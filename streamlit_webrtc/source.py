import asyncio
import fractions
import logging
import time
from typing import Callable, Optional, Union

import av
from aiortc import MediaStreamTrack
from aiortc.mediastreams import MediaStreamError

logger = logging.getLogger(__name__)

# Copied from https://github.com/aiortc/aiortc/blob/main/src/aiortc/mediastreams.py
AUDIO_PTIME = 0.020  # 20ms audio packetization
AUDIO_SAMPLE_RATE = 48000
AUDIO_TIME_BASE = fractions.Fraction(1, AUDIO_SAMPLE_RATE)
VIDEO_CLOCK_RATE = 90000
VIDEO_TIME_BASE = fractions.Fraction(1, VIDEO_CLOCK_RATE)


# Ref: VideoStreamTrack and AudioStreamTrack in
# https://github.com/aiortc/aiortc/blob/main/src/aiortc/mediastreams.py


VideoSourceCallback = Callable[
    [int, fractions.Fraction], av.VideoFrame
]  # (pts, time_base) -> frame

AudioSourceCallback = Callable[
    [int, fractions.Fraction], av.AudioFrame
]  # (pts, time_base) -> frame


class VideoSourceTrack(MediaStreamTrack):
    _on_ended_callback: Optional[Callable[[], None]]

    def __init__(self, callback: VideoSourceCallback, fps: Union[int, float]) -> None:
        super().__init__()
        self.kind = "video"
        self._callback = callback
        self._fps = fps
        self._started_at: Optional[float] = None
        self._pts: Optional[int] = None
        self._on_ended_callback = None
        self.on("ended", self._fire_on_ended)

    def _fire_on_ended(self) -> None:
        cb = self._on_ended_callback
        if cb is None:
            return
        try:
            cb()
        except Exception:
            logger.exception("VideoSourceTrack: on_ended callback raised an exception")

    async def recv(self) -> av.frame.Frame:
        if self.readyState != "live":
            raise MediaStreamError

        if self._started_at is None or self._pts is None:
            self._started_at = time.monotonic()
            self._pts = 0

            frame = self._call_callback(self._pts, VIDEO_TIME_BASE)
        else:
            self._pts += int(VIDEO_CLOCK_RATE / self._fps)

            frame = self._call_callback(self._pts, VIDEO_TIME_BASE)

            wait = self._started_at + (self._pts / VIDEO_CLOCK_RATE) - time.monotonic()
            if wait < 0:
                wait = 0
            await asyncio.sleep(wait)

        return frame

    def _call_callback(self, pts: int, time_base: fractions.Fraction) -> av.VideoFrame:
        # Per-call timing (not cumulative wall-clock drift): one late frame
        # mustn't keep tripping the warning on subsequent fast calls.
        callback_start = time.monotonic()
        try:
            frame = self._callback(pts, time_base)
        except Exception as exc:
            logger.error(
                "%s: Video frame callback raised an exception: %s",
                self.__class__.__name__,
                exc,
                exc_info=True,
            )
            raise
        callback_elapsed = time.monotonic() - callback_start

        frame_budget = 1.0 / self._fps
        if callback_elapsed > frame_budget:
            logger.warning(
                "%s: Video frame callback is too slow "
                "(%.1f ms > frame budget %.1f ms).",
                self.__class__.__name__,
                callback_elapsed * 1000,
                frame_budget * 1000,
            )

        frame.pts = pts
        frame.time_base = time_base
        return frame


class AudioSourceTrack(MediaStreamTrack):
    _on_ended_callback: Optional[Callable[[], None]]

    def __init__(
        self,
        callback: AudioSourceCallback,
        sample_rate: int = AUDIO_SAMPLE_RATE,
        ptime: float = AUDIO_PTIME,
    ) -> None:
        if sample_rate <= 0:
            raise ValueError(
                f"sample_rate must be a positive integer, got {sample_rate}"
            )
        super().__init__()
        self.kind = "audio"
        self._callback = callback
        self._sample_rate = sample_rate
        self._ptime = ptime
        self._samples_per_frame = int(self._sample_rate * self._ptime)
        self._time_base = fractions.Fraction(1, self._sample_rate)
        self._started_at: Optional[float] = None
        self._pts: Optional[int] = None
        self._on_ended_callback = None
        self.on("ended", self._fire_on_ended)

    def _fire_on_ended(self) -> None:
        cb = self._on_ended_callback
        if cb is None:
            return
        try:
            cb()
        except Exception:
            logger.exception("AudioSourceTrack: on_ended callback raised an exception")

    async def recv(self) -> av.frame.Frame:
        if self.readyState != "live":
            raise MediaStreamError

        if self._started_at is None or self._pts is None:
            self._started_at = time.monotonic()
            self._pts = 0

            frame = self._call_callback(self._pts, self._time_base)
        else:
            self._pts += self._samples_per_frame

            frame = self._call_callback(self._pts, self._time_base)

            wait = self._started_at + (self._pts / self._sample_rate) - time.monotonic()
            if wait < 0:
                wait = 0
            await asyncio.sleep(wait)

        return frame

    def _call_callback(self, pts: int, time_base: fractions.Fraction) -> av.AudioFrame:
        # Per-call timing (not cumulative wall-clock drift): one late frame
        # mustn't keep tripping the warning on subsequent fast calls.
        callback_start = time.monotonic()
        try:
            frame = self._callback(pts, time_base)
        except Exception as exc:
            logger.error(
                "%s: Audio frame callback raised an exception: %s",
                self.__class__.__name__,
                exc,
                exc_info=True,
            )
            raise
        callback_elapsed = time.monotonic() - callback_start

        if callback_elapsed > self._ptime:
            logger.warning(
                "%s: Audio frame callback is too slow (%.1f ms > ptime %.1f ms).",
                self.__class__.__name__,
                callback_elapsed * 1000,
                self._ptime * 1000,
            )

        frame.pts = pts
        frame.time_base = time_base
        return frame
