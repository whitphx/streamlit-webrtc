import asyncio
import itertools
import logging
import queue
import sys
import threading
import time
import traceback
from collections import deque
from typing import Generic, List, Optional, Union

import av
from aiortc import MediaStreamTrack
from aiortc.mediastreams import MediaStreamError

from .models import AudioProcessorT, FrameT, ProcessorT, VideoProcessorT

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class MediaProcessTrack(MediaStreamTrack, Generic[ProcessorT, FrameT]):
    def __init__(self, track: MediaStreamTrack, processor: ProcessorT):
        super().__init__()  # don't forget this!
        self.track = track
        self.processor: ProcessorT = processor

        @self.track.on("ended")
        def on_input_track_ended():
            logger.debug("Input track %s ended. Stop self %s", self.track, self)
            self.stop()

    async def recv(self):
        if self.readyState != "live":
            raise MediaStreamError

        frame = await self.track.recv()

        new_frame = self.processor.recv(frame)
        new_frame.pts = frame.pts
        new_frame.time_base = frame.time_base

        return new_frame

    def stop(self):
        super().stop()

        if hasattr(self.processor, "on_ended"):
            self.processor.on_ended()


class VideoProcessTrack(MediaProcessTrack[VideoProcessorT, av.VideoFrame]):
    kind = "video"
    processor: VideoProcessorT


class AudioProcessTrack(MediaProcessTrack[AudioProcessorT, av.AudioFrame]):
    kind = "audio"
    processor: AudioProcessorT


__SENTINEL__ = "__SENTINEL__"

# See https://stackoverflow.com/a/42007659
media_processing_thread_id_generator = itertools.count()


class AsyncMediaProcessTrack(MediaStreamTrack, Generic[ProcessorT, FrameT]):
    def __init__(
        self,
        track: MediaStreamTrack,
        processor: ProcessorT,
        stop_timeout: Optional[float] = None,
    ):
        super().__init__()  # don't forget this!

        self.track = track
        self.processor: ProcessorT = processor

        self._last_out_frame: Union[FrameT, None] = None

        self.stop_timeout = stop_timeout

        self._thread = None

    def _start(self):
        if self._thread:
            return

        self._in_queue: queue.Queue = queue.Queue()
        self._out_lock = threading.Lock()
        self._out_deque: deque = deque([])

        self._thread = threading.Thread(
            target=self._run_worker_thread,
            name=f"async_media_processor_{next(media_processing_thread_id_generator)}",
            daemon=True,
        )
        self._thread.start()

        @self.track.on("ended")
        def on_input_track_ended():
            logger.debug("Input track %s ended. Stop self %s", self.track, self)
            self.stop()

    def _run_worker_thread(self):
        try:
            self._worker_thread()
        except Exception:
            logger.error("Error occurred in the WebRTC thread:")

            exc_type, exc_value, exc_traceback = sys.exc_info()
            for tb in traceback.format_exception(exc_type, exc_value, exc_traceback):
                for tbline in tb.rstrip().splitlines():
                    logger.error(tbline.rstrip())

    async def _fallback_recv_queued(self, frames: List[FrameT]) -> FrameT:
        """
        Used as a fallback when the processor does not have its own `recv_queued`.
        """
        if len(frames) > 1:
            logger.warning(
                "Some frames have been dropped. "
                "`recv_queued` is recommended to use instead."
            )
        if self.processor.recv:
            return [self.processor.recv(frames[-1])]

        return frames[-1]

    def _worker_thread(self):
        loop = asyncio.new_event_loop()

        tasks: List[asyncio.Task] = []

        while True:
            # Read frames from the queue
            item = self._in_queue.get()
            if item == __SENTINEL__:
                break

            queued_frames = [item]

            stop_requested = False
            while not self._in_queue.empty():
                item = self._in_queue.get_nowait()
                if item == __SENTINEL__:
                    stop_requested = True
                    break
                else:
                    queued_frames.append(item)
            if stop_requested:
                break

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
            done, not_done = loop.run_until_complete(
                asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
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

            with self._out_lock:
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

        self.track.stop()
        self._in_queue.put(__SENTINEL__)
        self._thread.join(self.stop_timeout)

        if hasattr(self.processor, "on_ended"):
            self.processor.on_ended()

    async def recv(self):
        if self.readyState != "live":
            raise MediaStreamError

        self._start()

        frame = await self.track.recv()
        self._in_queue.put(frame)

        new_frame = None
        with self._out_lock:
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


class AsyncVideoProcessTrack(AsyncMediaProcessTrack[VideoProcessorT, av.VideoFrame]):
    kind = "video"
    processor: VideoProcessorT


class AsyncAudioProcessTrack(AsyncMediaProcessTrack[AudioProcessorT, av.AudioFrame]):
    kind = "audio"
    processor: AudioProcessorT
