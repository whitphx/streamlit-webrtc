import asyncio
import logging
import queue
from typing import Generic, List, Optional, TypeVar, Union

import av
from aiortc import MediaStreamTrack
from aiortc.mediastreams import MediaStreamError

logger = logging.getLogger(__name__)

# Type inference does not work on PyAV, which is a Python wrapper of C library.
# TODO: Write stubs
FrameT = TypeVar("FrameT", av.VideoFrame, av.AudioFrame)


# Inspired by `aiortc.contrib.media.MediaRecorder`:
# https://github.com/aiortc/aiortc/blob/2362e6d1f0c730a0f8c387bbea76546775ad2fe8/src/aiortc/contrib/media.py#L304  # noqa: E501
class MediaReceiver(Generic[FrameT]):
    _frames_queue: queue.Queue
    _track: Union[MediaStreamTrack, None]
    _task: Union[asyncio.Task, None]
    _frame_read: bool

    def __init__(self, queue_maxsize: int = 1) -> None:
        self._frames_queue = queue.Queue(maxsize=queue_maxsize)
        self._track = None
        self._task = None
        self._frame_read = False

    def addTrack(self, track: MediaStreamTrack):
        if self._track is not None:
            raise Exception(f"{self} already has a track {self._track}")

        self._track = track

    def hasTrack(self) -> bool:
        return self._track is not None

    def start(self):
        if self._task is not None:
            raise Exception(f"{self} has already a started task {self._task}")
        self._task = asyncio.ensure_future(self._run_track(self._track))

    def stop(self):
        if self._task is not None:
            self._task.cancel()
            self._task = None

    def get_frame(self, block: bool = True, timeout: Optional[float] = None) -> FrameT:
        self._frame_read = True

        return self._frames_queue.get(block=block, timeout=timeout)

    def get_frames(
        self, block: bool = True, timeout: Optional[float] = None
    ) -> List[FrameT]:
        self._frame_read = True

        if self._frames_queue.empty():
            return [self.get_frame(block=block, timeout=timeout)]

        frames: List[FrameT] = []
        while not self._frames_queue.empty():
            frames.append(self._frames_queue.get_nowait())
        return frames

    async def _run_track(self, track: MediaStreamTrack):
        while True:
            try:
                frame = await track.recv()
            except MediaStreamError:
                return
            # TODO: Find more performant way
            if self._frames_queue.full():
                if self._frame_read:
                    logger.warning(
                        "Queue overflow. Consider to set receiver size bigger. "
                        "Current size is %d.",
                        self._frames_queue.maxsize,
                    )
                self._frames_queue.get_nowait()
            self._frames_queue.put(frame)


VideoReceiver = MediaReceiver[av.VideoFrame]
AudioReceiver = MediaReceiver[av.AudioFrame]
