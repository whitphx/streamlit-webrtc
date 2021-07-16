import abc
import logging
from typing import Callable, Generic, List, TypeVar

import av
import numpy as np
from aiortc.contrib.media import MediaPlayer, MediaRecorder

logger = logging.getLogger(__name__)


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


VideoProcessorT = TypeVar("VideoProcessorT", bound=VideoProcessorBase)
AudioProcessorT = TypeVar("AudioProcessorT", bound=AudioProcessorBase)

MediaPlayerFactory = Callable[[], MediaPlayer]
MediaRecorderFactory = Callable[[], MediaRecorder]
VideoProcessorFactory = Callable[[], VideoProcessorT]
AudioProcessorFactory = Callable[[], AudioProcessorT]

ProcessorT = TypeVar("ProcessorT", VideoProcessorBase, AudioProcessorBase)
FrameT = TypeVar("FrameT", av.VideoFrame, av.AudioFrame)


class MixerBase(abc.ABC, Generic[FrameT]):
    @abc.abstractmethod
    def on_update(self, frames: List[FrameT]) -> FrameT:
        """
        Receives frames from input tracks and returns one frame to output.
        """


MixerT = TypeVar("MixerT", bound=MixerBase)
