import asyncio
import queue
from typing import Union

from aiortc import MediaStreamTrack
from aiortc.mediastreams import MediaStreamError


# Inspired by `aiortc.contrib.media.MediaRecorder`:
# https://github.com/aiortc/aiortc/blob/2362e6d1f0c730a0f8c387bbea76546775ad2fe8/src/aiortc/contrib/media.py#L304  # noqa: E501
class VideoReceiver:
    _frames_queue: queue.Queue
    _track: Union[MediaStreamTrack, None]
    _task: Union[asyncio.Task, None]

    @property
    def frames_queue(self) -> queue.Queue:
        return self._frames_queue

    def __init__(self, queue_maxsize: int = 1) -> None:
        self._frames_queue = queue.Queue(maxsize=queue_maxsize)
        self._track = None
        self._task = None

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

    async def _run_track(self, track: MediaStreamTrack):
        while True:
            try:
                frame = await track.recv()
            except MediaStreamError:
                return
            self.frames_queue.put(frame)
