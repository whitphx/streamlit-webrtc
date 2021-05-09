import abc
import asyncio
import itertools
import logging
import queue
import sys
import threading
import time
import traceback
from collections import deque
from typing import Generic, List, Optional, TypeVar, Union

import av
import numpy as np
from aiortc import MediaStreamTrack

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class VideoProcessorBase(abc.ABC):
    """
    A base class for video processors.
    """

    def transform(self, frame: av.VideoFrame) -> np.ndarray:
        """
        Receives a video frame, and returns a numpy array representing
        an image for a new frame in bgr24 format.

        .. deprecated:: 0.20.0
        """
        raise NotImplementedError("transform() is not implemented.")

    def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
        """
        Receives a video frame, and returns a new video frame.

        When running in async mode, only the latest frame is provided and
        other frames are dropped which have arrived after the previous recv() call
        and before the latest one.
        In order to process all the frames, use recv_queued() instead.
        """
        logger.warning("transform() is deprecated. Implement recv() instead.")
        new_image = self.transform(frame)
        return av.VideoFrame.from_ndarray(new_image, format="bgr24")

    async def recv_queued(self, frames: List[av.AudioFrame]) -> av.VideoFrame:
        """
        Receives all the frames arrived after the previous recv_queued() call
        and returns new frames when running in async mode.
        If not implemented, delegated to the recv() method by default.
        """
        return [self.recv(frames[-1])]


class VideoTransformerBase(VideoProcessorBase):  # Backward compatiblity
    """
    A base class for video transformers.
    This interface is deprecated. Use VideoProcessorBase instead.

    .. deprecated:: 0.20.0
    """


class AudioProcessorBase(abc.ABC):
    """
    A base class for audio processors.
    """

    def recv(self, frame: av.AudioFrame) -> av.AudioFrame:
        """
        Receives a audio frame, and returns a new audio frame.

        When running in async mode, only the latest frame is provided and
        other frames are dropped which have arrived after the previous recv() call
        and before the latest one.
        In order to process all the frames, use recv_queued() instead.
        """
        raise NotImplementedError("recv() is not implemented.")

    async def recv_queued(self, frames: List[av.AudioFrame]) -> av.AudioFrame:
        """
        Receives all the frames arrived after the previous recv_queued() call
        and returns new frames when running in async mode.
        If not implemented, delegated to the recv() method by default.
        """
        if len(frames) > 1:
            logger.warning(
                "Some frames have been dropped during audio processing. "
                "`recv_queued` is recommended to use instead."
            )
        return [self.recv(frames[-1])]


ProcessorT = TypeVar("ProcessorT", VideoProcessorBase, AudioProcessorBase)
FrameT = TypeVar("FrameT", av.VideoFrame, av.AudioFrame)


class MediaProcessTrack(MediaStreamTrack, Generic[ProcessorT, FrameT]):
    def __init__(self, track: MediaStreamTrack, processor: ProcessorT):
        super().__init__()  # don't forget this!
        self.track = track
        self.processor: ProcessorT = processor

    async def recv(self):
        frame = await self.track.recv()

        new_frame = self.processor.recv(frame)
        new_frame.pts = frame.pts
        new_frame.time_base = frame.time_base

        return new_frame


class VideoProcessTrack(MediaProcessTrack[AudioProcessorBase, av.AudioFrame]):
    kind = "video"


class AudioProcessTrack(MediaProcessTrack[AudioProcessorBase, av.AudioFrame]):
    kind = "audio"


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

        self._thread = threading.Thread(
            target=self._run_worker_thread,
            name=f"async_media_processor_{next(media_processing_thread_id_generator)}",
        )
        self._in_queue: queue.Queue = queue.Queue()

        self._out_lock = threading.Lock()
        self._out_deque: deque = deque([])
        self._last_out_frame: Union[FrameT, None] = None

        self._thread.start()

        self.stop_timeout = stop_timeout

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
        return [self.processor.recv(frames[-1])]

    def _worker_thread(self):
        loop = asyncio.new_event_loop()

        futures: List[asyncio.futures.Future] = []

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

            # Set up a future, providing the frames.
            if hasattr(self.processor, "recv_queued"):
                coro = self.processor.recv_queued(queued_frames)
            else:
                coro = self._fallback_recv_queued(queued_frames)

            future = asyncio.ensure_future(coro, loop=loop)
            futures.append(future)

            # NOTE: If the execution time of recv_queued() increases
            #       with the length of the input frames,
            #       it increases exponentially over the calls.
            #       Then, the execution time has to be monitored.
            start_time = time.monotonic()
            done, not_done = loop.run_until_complete(
                asyncio.wait(futures, return_when=asyncio.FIRST_COMPLETED)
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
                raise Exception("Unexpectedly multiple futures have finished")

            done_idx = futures.index(future)
            old_futures = futures[:done_idx]
            for old_future in old_futures:
                logger.info("Cancel an old future %s", future)
                old_future.cancel()
            futures = [f for f in futures if not f.done()]

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
        self._in_queue.put(__SENTINEL__)
        self._thread.join(self.stop_timeout)

        return super().stop()

    async def recv(self):
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


class AsyncVideoProcessTrack(AsyncMediaProcessTrack[VideoProcessorBase, av.VideoFrame]):
    kind = "video"


class AsyncAudioProcessTrack(AsyncMediaProcessTrack[AudioProcessorBase, av.AudioFrame]):
    kind = "audio"
