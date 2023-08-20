import asyncio
import fractions
import logging
import queue
import time
from typing import Optional

import av
import numpy as np
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


class VideoSourceTrack(MediaStreamTrack):
    _buffer: np.ndarray
    _queue: "queue.Queue[np.ndarray]"

    _started_at: Optional[float]
    _pts: Optional[int]

    def __init__(self, init_buffer: np.ndarray) -> None:
        super().__init__()
        self.kind = "video"
        self._buffer = init_buffer
        self._queue = queue.Queue()
        self._started_at = None
        self._pts = None

    async def recv(self) -> av.frame.Frame:
        if self.readyState != "live":
            raise MediaStreamError

        if self._started_at is None or self._pts is None:
            self._started_at = time.monotonic()
            self._pts = 0
        else:
            self._pts += int(VIDEO_PTIME * VIDEO_CLOCK_RATE)
            wait = self._started_at + (self._pts / VIDEO_CLOCK_RATE) - time.monotonic()
            await asyncio.sleep(wait)

        try:
            buffer = self._queue.get_nowait()
            self._buffer = buffer
        except queue.Empty:
            buffer = self._buffer

        frame = av.VideoFrame.from_ndarray(
            buffer, format="bgr24"
        )  # TODO: Provide a way for developers to configure the arguments like `format`
        frame.pts = self._pts
        frame.time_base = VIDEO_TIME_BASE
        return frame
