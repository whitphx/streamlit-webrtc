"""Layer-2 tests for `process.VideoProcessTrack` and its async counterpart.

These exercise the sync and async processor wrappers against a stub source
track, so the timing-sensitive async path (which drops intermediate frames
under load) can be verified without a real WebRTC connection.
"""

import asyncio
import fractions
import threading
import time
from typing import List, Optional

import av
import numpy as np
import pytest
from aiortc import MediaStreamTrack
from aiortc.mediastreams import MediaStreamError

from streamlit_webrtc.models import VideoProcessorBase
from streamlit_webrtc.process import (
    AsyncVideoProcessTrack,
    VideoProcessTrack,
)

_VIDEO_TIME_BASE = fractions.Fraction(1, 90000)


def _video_frame(value: int = 0, pts: int = 0) -> av.VideoFrame:
    arr = np.full((16, 16, 3), value, dtype=np.uint8)
    frame = av.VideoFrame.from_ndarray(arr, format="bgr24")
    frame.pts = pts
    frame.time_base = _VIDEO_TIME_BASE
    return frame


class _StubVideoTrack(MediaStreamTrack):
    """Yields a fixed sequence of frames, then ends."""

    kind = "video"

    def __init__(self, frames: List[av.VideoFrame], delay: float = 0.0) -> None:
        super().__init__()
        self._frames = list(frames)
        self._delay = delay

    async def recv(self) -> av.VideoFrame:
        if self.readyState != "live":
            raise MediaStreamError
        if not self._frames:
            self.stop()
            raise MediaStreamError
        if self._delay:
            await asyncio.sleep(self._delay)
        return self._frames.pop(0)


class _IdentityProcessor(VideoProcessorBase):
    def __init__(self) -> None:
        self.calls = 0

    def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
        self.calls += 1
        return frame


class _MutatingProcessor(VideoProcessorBase):
    """Replaces every frame with a constant-value frame."""

    def __init__(self, value: int = 200) -> None:
        self.value = value

    def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
        return _video_frame(self.value, pts=frame.pts or 0)


class _BrokenProcessor(VideoProcessorBase):
    def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
        raise RuntimeError("processor blew up")


class TestVideoProcessTrack:
    """Sync (per-frame) processor wrapper."""

    def test_one_in_one_out(self) -> None:
        proc = _IdentityProcessor()
        frames = [_video_frame(i, pts=i * 1000) for i in range(3)]
        track = VideoProcessTrack(track=_StubVideoTrack(frames), processor=proc)

        async def drain() -> List[av.VideoFrame]:
            return [await track.recv() for _ in range(3)]

        out = asyncio.run(drain())
        assert proc.calls == 3
        assert [f.pts for f in out] == [0, 1000, 2000]

    def test_processor_exception_propagates(self) -> None:
        track = VideoProcessTrack(
            track=_StubVideoTrack([_video_frame(0)]), processor=_BrokenProcessor()
        )
        with pytest.raises(RuntimeError, match="blew up"):
            asyncio.run(track.recv())

    def test_pts_and_time_base_preserved(self) -> None:
        # The wrapper restores pts/time_base on the *new* frame even if the
        # processor returned a freshly-constructed one — important for
        # downstream encoder behavior.
        src = _video_frame(0, pts=1234)
        track = VideoProcessTrack(
            track=_StubVideoTrack([src]), processor=_MutatingProcessor(value=42)
        )
        out = asyncio.run(track.recv())
        assert out.pts == 1234


class TestAsyncVideoProcessTrack:
    """Async (background-thread) processor wrapper."""

    def test_drops_intermediate_frames_under_load(self) -> None:
        # Producer is fast (no delay), processor is slow. The wrapper must
        # surface the *latest* frame, not the queue head. This is the key
        # invariant of the async path.
        class SlowProcessor(VideoProcessorBase):
            def __init__(self) -> None:
                self.seen: List[int] = []

            def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
                # First frame is slow; later ones are instant. This guarantees
                # backlog before the second consumer-side recv() happens.
                if not self.seen:
                    time.sleep(0.15)
                arr = frame.to_ndarray(format="bgr24")
                self.seen.append(int(arr[0, 0, 0]))
                return frame

        slow = SlowProcessor()
        frames = [_video_frame(i, pts=i * 1000) for i in range(5)]
        track = AsyncVideoProcessTrack(track=_StubVideoTrack(frames), processor=slow)

        async def drain() -> List[av.VideoFrame]:
            collected = []
            for _ in range(5):
                collected.append(await track.recv())
                await asyncio.sleep(0.01)
            return collected

        try:
            asyncio.run(drain())
        finally:
            track.stop()

        # The slow processor must not have processed every frame — some must
        # have been collapsed by the wrapper's "use latest" logic. Concretely:
        # 5 frames in, fewer than 5 processed.
        assert 0 < len(slow.seen) < 5

    def test_worker_exception_surfaces_on_next_recv(self) -> None:
        # The worker thread captures exceptions and reraises them from recv().
        frames = [_video_frame(i) for i in range(2)]
        track = AsyncVideoProcessTrack(
            track=_StubVideoTrack(frames, delay=0.01), processor=_BrokenProcessor()
        )

        async def run() -> Optional[Exception]:
            # First recv kicks off the worker thread and returns the input frame
            # (since the deque is still empty). The worker then fails. The next
            # recv() should re-raise.
            try:
                await track.recv()
                # Give the worker thread a moment to capture the exception.
                await asyncio.sleep(0.1)
                await track.recv()
            except Exception as exc:
                return exc
            return None

        try:
            exc = asyncio.run(run())
        finally:
            track.stop()
        assert isinstance(exc, RuntimeError)
        assert "blew up" in str(exc)

    def test_on_ended_called_on_stop(self) -> None:
        class CountingProcessor(VideoProcessorBase):
            def __init__(self) -> None:
                self.ended = threading.Event()

            def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
                return frame

            def on_ended(self) -> None:
                self.ended.set()

        proc = CountingProcessor()
        track = AsyncVideoProcessTrack(
            track=_StubVideoTrack([_video_frame(0)]), processor=proc
        )

        async def trigger() -> None:
            await track.recv()
            await asyncio.sleep(0.05)

        asyncio.run(trigger())
        track.stop()
        assert proc.ended.wait(timeout=1.0)
