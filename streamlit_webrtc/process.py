import asyncio
import itertools
import logging
import time
from collections import deque
from typing import Generic, List, Optional, Union

import av
from aiortc import MediaStreamTrack
from aiortc.mediastreams import MediaStreamError

from .models import (
    AudioProcessorBase,
    AudioProcessorT,
    FrameT,
    ProcessorT,
    VideoProcessorBase,
    VideoProcessorT,
)

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class MediaProcessTrack(MediaStreamTrack, Generic[ProcessorT, FrameT]):
    def __init__(self, track: MediaStreamTrack, processor: ProcessorT):
        super().__init__()  # don't forget this!
        self.track = track
        self.processor: ProcessorT = processor

    async def recv(self):
        if self.readyState != "live":
            raise MediaStreamError

        frame = await self.track.recv()

        new_frame = self.processor.recv(frame)
        new_frame.pts = frame.pts
        new_frame.time_base = frame.time_base

        return new_frame


class VideoProcessTrack(
    MediaProcessTrack[VideoProcessorBase, av.VideoFrame], Generic[VideoProcessorT]
):
    kind = "video"
    processor: VideoProcessorT


class AudioProcessTrack(
    MediaProcessTrack[AudioProcessorBase, av.AudioFrame], Generic[AudioProcessorT]
):
    kind = "audio"
    processor: AudioProcessorT


# See https://stackoverflow.com/a/42007659
media_processing_thread_id_generator = itertools.count()


class AsyncMediaProcessTrack(MediaStreamTrack, Generic[ProcessorT, FrameT]):
    track: MediaStreamTrack
    processor: ProcessorT
    stop_timeout: Optional[float]

    _last_out_frame: Union[FrameT, None]

    _task: Optional[asyncio.Task]
    _in_queue: asyncio.Queue
    _out_lock: asyncio.Lock
    _out_deque: deque

    def __init__(
        self,
        track: MediaStreamTrack,
        processor: ProcessorT,
        stop_timeout: Optional[float] = None,
    ):
        super().__init__()  # don't forget this!

        self.track = track
        self.processor = processor
        self.stop_timeout = stop_timeout

        self._last_out_frame = None

        self._in_queue = asyncio.Queue()
        self._out_lock = asyncio.Lock()
        self._out_deque: deque = deque([])
        self._task = None

    def _start(self):
        if self._task:
            return

        loop = asyncio.get_event_loop()
        self._task = loop.create_task(self._worker_coro())

        @self.track.on("ended")
        def on_input_track_ended():
            logger.debug("Input track %s ended. Stop self %s", self.track, self)
            self.stop()

    async def _fallback_recv_queued(self, frames: List[FrameT]) -> FrameT:
        """
        Used as a fallback when the processor does not have its own `recv_queued`.
        """
        if len(frames) > 1:
            logger.warning(
                "Some frames have been dropped. "
                "`recv_queued` is recommended to use instead."
            )
        return [self.processor.recv(frames[-1])]

    async def _worker_coro(self):
        loop = asyncio.get_event_loop()

        tasks: List[asyncio.Task] = []

        while True:
            # Read frames from the queue
            queued_frame = await self._in_queue.get()
            queued_frames = [queued_frame]
            while not self._in_queue.empty():
                queued_frame = self._in_queue.get_nowait()
                queued_frames.append(queued_frame)

            if len(queued_frames) == 0:
                raise Exception("Unexpectedly, queued frames do not exist")

            # Set up a task, providing the frames.
            if hasattr(self.processor, "recv_queued"):
                coro = self.processor.recv_queued(queued_frames)
            else:
                coro = self._fallback_recv_queued(queued_frames)

            task = loop.create_task(coro=coro)
            tasks.append(task)

            # NOTE: If the execution time of recv_queued() increases
            #       with the length of the input frames,
            #       it increases exponentially over the calls.
            #       Then, the execution time has to be monitored.
            start_time = time.monotonic()
            done, not_done = await asyncio.wait(
                tasks, return_when=asyncio.FIRST_COMPLETED
            )
            elapsed_time = time.monotonic() - start_time

            if (
                elapsed_time > 10
            ):  # No reason for 10 seconds... It's an ad-hoc decision.
                raise Exception(
                    "recv_queued() or recv() is taking too long to execute, "
                    f"{elapsed_time}s."
                )

            if len(done) > 1:
                raise Exception("Unexpectedly multiple tasks have finished")

            done_idx = tasks.index(task)
            old_tasks = tasks[:done_idx]
            for old_task in old_tasks:
                logger.info("Cancel an old task %s", task)
                old_task.cancel()
            tasks = [t for t in tasks if not t.done()]

            finished = done.pop()
            new_frames = finished.result()

            async with self._out_lock:
                if len(self._out_deque) > 1:
                    logger.warning(
                        "Not all the queued frames have been consumed, "
                        "which means the processing and consuming threads "
                        "seem not to be synchronized."
                    )
                    firstitem = self._out_deque.popleft()
                    self._out_deque.clear()
                    self._out_deque.append(firstitem)

                self._out_deque.extend(new_frames)

    def stop(self):
        super().stop()

        self._task.cancel()

    async def recv(self):
        if self.readyState != "live":
            raise MediaStreamError

        self._start()

        frame = await self.track.recv()
        self._in_queue.put_nowait(frame)

        new_frame = None
        async with self._out_lock:
            if len(self._out_deque) > 0:
                new_frame = self._out_deque.popleft()

        if new_frame is None:
            new_frame = self._last_out_frame

        if new_frame:
            self._last_out_frame = new_frame
            new_frame.pts = frame.pts
            new_frame.time_base = frame.time_base

            return new_frame

        return frame


class AsyncVideoProcessTrack(
    AsyncMediaProcessTrack[VideoProcessorBase, av.VideoFrame], Generic[VideoProcessorT]
):
    kind = "video"
    processor: VideoProcessorT


class AsyncAudioProcessTrack(
    AsyncMediaProcessTrack[AudioProcessorBase, av.AudioFrame], Generic[AudioProcessorT]
):
    kind = "audio"
    processor: AudioProcessorT
