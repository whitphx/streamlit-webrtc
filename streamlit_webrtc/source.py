import asyncio
import fractions
import logging
import time
from typing import Callable, Optional

import av
from aiortc import MediaStreamTrack
from aiortc.mediastreams import MediaStreamError

logger = logging.getLogger(__name__)

# TODO: Now these values are just copied from mediastreams.py linked below, but should be made configurable.  # noqa: E501
# https://github.com/aiortc/aiortc/blob/main/src/aiortc/mediastreams.py
AUDIO_PTIME = 0.020  # 20ms audio packetization
VIDEO_CLOCK_RATE = 90000
VIDEO_PTIME = 1 / 30  # 30fps
VIDEO_TIME_BASE = fractions.Fraction(1, VIDEO_CLOCK_RATE)


# Ref: VideoStreamTrack and AudioStreamTrack in
# https://github.com/aiortc/aiortc/blob/main/src/aiortc/mediastreams.py


VideoSourceCallback = Callable[[], av.VideoFrame]


class VideoSourceTrack(MediaStreamTrack):
    _callback: VideoSourceCallback

    _started_at: Optional[float]
    _pts: Optional[int]

    def __init__(self, callback: VideoSourceCallback) -> None:
        super().__init__()
        self.kind = "video"
        self._callback = callback
        self._started_at = None
        self._pts = None

    def _set_callback(self, callback: VideoSourceCallback) -> None:
        self._callback = callback

    async def recv(self) -> av.frame.Frame:
        if self.readyState != "live":
            raise MediaStreamError

        frame = self._callback()

        if self._started_at is None or self._pts is None:
            self._started_at = time.monotonic()
            self._pts = 0
        else:
            self._pts += int(VIDEO_PTIME * VIDEO_CLOCK_RATE)
            wait = self._started_at + (self._pts / VIDEO_CLOCK_RATE) - time.monotonic()
            if wait < 0:
                logger.warning(
                    "VideoSourceCallbackTrack: Video frame callback is too slow."
                )
                wait = 0
            await asyncio.sleep(wait)

        frame.pts = self._pts
        frame.time_base = VIDEO_TIME_BASE
        return frame
