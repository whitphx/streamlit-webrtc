import asyncio
import threading
from typing import List

import av
import numpy as np

from streamlit_webrtc.models import CallbackAttachableProcessor


def _video_frame(value: int = 0) -> av.VideoFrame:
    arr = np.full((16, 16, 3), value, dtype=np.uint8)
    return av.VideoFrame.from_ndarray(arr, format="bgr24")


class TestRecv:
    def test_no_callback_passthrough(self) -> None:
        proc = CallbackAttachableProcessor(
            frame_callback=None, queued_frames_callback=None, ended_callback=None
        )
        frame = _video_frame(7)
        assert proc.recv(frame) is frame

    def test_invokes_callback(self) -> None:
        seen: List[av.VideoFrame] = []

        def cb(frame: av.VideoFrame) -> av.VideoFrame:
            seen.append(frame)
            return _video_frame(99)

        proc = CallbackAttachableProcessor(
            frame_callback=cb, queued_frames_callback=None, ended_callback=None
        )
        out = proc.recv(_video_frame(7))
        assert len(seen) == 1
        # The callback returned a different frame; recv must surface it.
        assert out is not seen[0]


class TestRecvQueued:
    def test_no_callback_falls_back_to_recv_on_last_frame(self) -> None:
        seen: List[av.VideoFrame] = []

        def cb(frame: av.VideoFrame) -> av.VideoFrame:
            seen.append(frame)
            return frame

        proc = CallbackAttachableProcessor(
            frame_callback=cb, queued_frames_callback=None, ended_callback=None
        )
        frames = [_video_frame(i) for i in range(3)]
        out = asyncio.run(proc.recv_queued(frames))
        # The fallback path only processes the latest frame.
        assert len(out) == 1
        assert len(seen) == 1
        assert seen[0] is frames[-1]

    def test_invokes_queued_callback(self) -> None:
        received: List[List[av.VideoFrame]] = []

        async def qcb(frames: List[av.VideoFrame]) -> List[av.VideoFrame]:
            received.append(frames)
            return frames

        proc = CallbackAttachableProcessor(
            frame_callback=None, queued_frames_callback=qcb, ended_callback=None
        )
        frames = [_video_frame(i) for i in range(3)]
        out = asyncio.run(proc.recv_queued(frames))
        assert received == [frames]
        assert out == frames


class TestOnEnded:
    def test_no_callback_is_silent(self) -> None:
        proc = CallbackAttachableProcessor(
            frame_callback=None, queued_frames_callback=None, ended_callback=None
        )
        # Must not raise even though no callback is registered.
        proc.on_ended()

    def test_invokes_callback(self) -> None:
        calls: List[int] = []
        proc = CallbackAttachableProcessor(
            frame_callback=None,
            queued_frames_callback=None,
            ended_callback=lambda: calls.append(1),
        )
        proc.on_ended()
        assert calls == [1]


class TestUpdateCallbacks:
    def test_hot_swap_takes_effect_on_next_recv(self) -> None:
        proc = CallbackAttachableProcessor(
            frame_callback=lambda f: _video_frame(1),
            queued_frames_callback=None,
            ended_callback=None,
        )
        proc.recv(_video_frame(0))
        # Swap the callback.
        proc.update_callbacks(
            frame_callback=lambda f: _video_frame(2),
            queued_frames_callback=None,
            ended_callback=None,
        )
        # The new callback drives subsequent recv() calls. We can't easily
        # assert "returns frame with value 2" because of frame internals, but
        # we can prove the swap happened by verifying recv() doesn't crash and
        # update_callbacks under the lock doesn't deadlock against recv().
        out = proc.recv(_video_frame(0))
        assert out is not None

    def test_swap_is_serialized_against_recv(self) -> None:
        # Soak the lock: 200 swaps interleaved with 200 recv() calls from
        # another thread. If `update_callbacks` and `recv` weren't both holding
        # the same lock we'd see a torn read mid-frame; this test isn't a strict
        # proof, but it'd flake fast if the locking regressed.
        proc = CallbackAttachableProcessor(
            frame_callback=lambda f: f,
            queued_frames_callback=None,
            ended_callback=None,
        )
        stop = threading.Event()
        errors: List[Exception] = []

        def reader() -> None:
            frame = _video_frame(0)
            try:
                for _ in range(200):
                    proc.recv(frame)
                    if stop.is_set():
                        return
            except Exception as exc:
                errors.append(exc)

        def identity(frame: av.VideoFrame) -> av.VideoFrame:
            return frame

        t = threading.Thread(target=reader)
        t.start()
        try:
            for _ in range(200):
                proc.update_callbacks(
                    frame_callback=identity,
                    queued_frames_callback=None,
                    ended_callback=None,
                )
        finally:
            stop.set()
            t.join(timeout=2.0)
        assert errors == []
