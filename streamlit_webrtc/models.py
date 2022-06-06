import abc
import logging
import threading
from typing import Awaitable, Callable, Generic, List, Optional, TypeVar

import av
import numpy as np
from aiortc.contrib.media import MediaPlayer, MediaRecorder

logger = logging.getLogger(__name__)


VideoFrameCallback = Callable[[av.VideoFrame], av.VideoFrame]
QueuedVideoFramesCallback = Callable[
    [List[av.VideoFrame]], Awaitable[List[av.VideoFrame]]
]
AudioFrameCallback = Callable[[av.AudioFrame], av.AudioFrame]
QueuedAudioFramesCallback = Callable[
    [List[av.AudioFrame]], Awaitable[List[av.AudioFrame]]
]
MediaEndedCallback = Callable[[], None]


class ProcessorBase(abc.ABC):
    def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
        raise NotImplementedError()

    async def recv_queued(self, frames: List[av.VideoFrame]) -> List[av.VideoFrame]:
        raise NotImplementedError()

    def on_ended(self):
        raise NotImplementedError()


class CallbackAttachableProcessor(ProcessorBase):
    frame_callback: Optional[VideoFrameCallback]
    queued_frames_callback: Optional[QueuedVideoFramesCallback]
    media_ended_callback: Optional[MediaEndedCallback]

    def __init__(
        self,
        frame_callback: Optional[VideoFrameCallback],
        queued_frames_callback: Optional[QueuedVideoFramesCallback],
        ended_callback: Optional[MediaEndedCallback],
    ) -> None:
        self._lock = threading.Lock()
        self.frame_callback = frame_callback
        self.queued_frames_callback = queued_frames_callback
        self.media_ended_callback = ended_callback

    def update_callbacks(
        self,
        frame_callback: Optional[VideoFrameCallback],
        queued_frames_callback: Optional[QueuedVideoFramesCallback],
        ended_callback: Optional[MediaEndedCallback],
    ) -> None:
        with self._lock:
            self.frame_callback = frame_callback
            self.queued_frames_callback = queued_frames_callback
            self.media_ended_callback = ended_callback

    def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
        with self._lock:
            if self.frame_callback:
                return self.frame_callback(frame)

        return frame

    async def recv_queued(self, frames: List[av.VideoFrame]) -> List[av.VideoFrame]:
        with self._lock:
            if self.queued_frames_callback:
                return await self.queued_frames_callback(frames)

        return [self.recv(frames[-1])]

    def on_ended(self):
        with self._lock:
            if self.media_ended_callback:
                return self.media_ended_callback()


class VideoProcessorBase(ProcessorBase):
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

    async def recv_queued(self, frames: List[av.VideoFrame]) -> List[av.VideoFrame]:
        """
        Receives all the frames arrived after the previous recv_queued() call
        and returns new frames when running in async mode.
        If not implemented, delegated to the recv() method by default.
        """
        return [self.recv(frames[-1])]

    def on_ended(self):
        """
        A callback method which is called when the input track ends.
        """


class VideoTransformerBase(VideoProcessorBase):  # Backward compatiblity
    """
    A base class for video transformers.
    This interface is deprecated. Use VideoProcessorBase instead.

    .. deprecated:: 0.20.0
    """


class AudioProcessorBase(ProcessorBase):
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

    async def recv_queued(self, frames: List[av.AudioFrame]) -> List[av.AudioFrame]:
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

    def on_ended(self):
        """
        A callback method which is called when the input track ends.
        """


VideoProcessorT = TypeVar("VideoProcessorT", bound=VideoProcessorBase)
AudioProcessorT = TypeVar("AudioProcessorT", bound=AudioProcessorBase)

MediaPlayerFactory = Callable[[], MediaPlayer]
MediaRecorderFactory = Callable[[], MediaRecorder]
VideoProcessorFactory = Callable[[], VideoProcessorT]
AudioProcessorFactory = Callable[[], AudioProcessorT]

ProcessorT = TypeVar("ProcessorT", bound=ProcessorBase)
FrameT = TypeVar("FrameT", av.VideoFrame, av.AudioFrame)


class MixerBase(abc.ABC, Generic[FrameT]):
    @abc.abstractmethod
    def on_update(self, frames: List[FrameT]) -> FrameT:
        """
        Receives frames from input tracks and returns one frame to output.
        """


MixerT = TypeVar("MixerT", bound=MixerBase)
