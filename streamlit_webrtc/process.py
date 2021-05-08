import abc
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
    def transform(self, frame: av.VideoFrame) -> np.ndarray:
        """@deprecated Backward compatibility;
        Returns a new video frame in bgr24 format"""
        raise NotImplementedError("transform() is not implemented.")

    def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
        """ Processes the received frame and returns a new frame """
        logger.warning("transform() is deprecated. Implement recv() instead.")
        new_image = self.transform(frame)
        return av.VideoFrame.from_ndarray(new_image, format="bgr24")

    def recv_queued(self, frames: List[av.AudioFrame]) -> av.VideoFrame:
        """Processes all the frames received and queued since the previous call in async mode.
        If not implemented, delegated to recv() by default."""
        return [self.recv(frames[-1])]


VideoTransformerBase = VideoProcessorBase  # Backward compatiblity


class AudioProcessorBase(abc.ABC):
    def recv(self, frame: av.AudioFrame) -> av.AudioFrame:
        """ Processes the received frame and returns a new frame """
        raise NotImplementedError("recv() is not implemented.")

    def recv_queued(self, frames: List[av.AudioFrame]) -> av.AudioFrame:
        """Processes all the frames received and queued since the previous call in async mode.
        If not implemented, delegated to recv() by default."""
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

    def _worker_thread(self):
        while True:
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

            # NOTE: If the execution time of recv_queued() increases
            #       with the length of the input frames,
            #       it increases exponentially over the calls.
            #       Then, the execution time has to be monitored.
            start_time = time.monotonic()
            new_frames = self.processor.recv_queued(queued_frames)
            elapsed_time = time.monotonic() - start_time

            if (
                elapsed_time > 10
            ):  # No reason for 10 seconds... It's an ad-hoc decision.
                raise Exception(
                    "recv_queued() or recv() is taking too long to execute, "
                    f"{elapsed_time}s."
                )

            with self._out_lock:
                for new_frame in new_frames:
                    self._out_deque.append(new_frame)

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
