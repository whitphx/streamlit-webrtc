import abc
import logging
import threading
from typing import Any, Awaitable, Callable, Generic, List, Optional, TypeVar, Union

import av
import numpy as np
from aiortc.contrib.media import MediaPlayer, MediaRecorder

logger = logging.getLogger(__name__)

FrameT = TypeVar("FrameT", av.VideoFrame, av.AudioFrame)

FrameCallback = Callable[[FrameT], FrameT]
QueuedFramesCallback = Callable[[List[FrameT]], Awaitable[List[FrameT]]]
VideoFrameCallback = FrameCallback[av.VideoFrame]
QueuedVideoFramesCallback = QueuedFramesCallback[av.VideoFrame]
AudioFrameCallback = FrameCallback[av.AudioFrame]
QueuedAudioFramesCallback = QueuedFramesCallback[av.AudioFrame]
MediaEndedCallback = Callable[[], None]


class ProcessorBase(abc.ABC, Generic[FrameT]):
    def recv(self, frame: FrameT) -> FrameT:
        raise NotImplementedError()

    async def recv_queued(self, frames: List[FrameT]) -> List[FrameT]:
        raise NotImplementedError()

    def on_ended(self):
        raise NotImplementedError()


class CallbackAttachableProcessor(ProcessorBase[FrameT]):
    _lock: threading.Lock
    _frame_callback: Optional[FrameCallback[FrameT]]
    _queued_frames_callback: Optional[QueuedFramesCallback[FrameT]]
    _media_ended_callback: Optional[MediaEndedCallback]

    def __init__(
        self,
        frame_callback: Optional[FrameCallback[FrameT]],
        queued_frames_callback: Optional[QueuedFramesCallback[FrameT]],
        ended_callback: Optional[MediaEndedCallback],
    ) -> None:
        self._lock = threading.Lock()
        self._frame_callback = frame_callback
        self._queued_frames_callback = queued_frames_callback
        self._media_ended_callback = ended_callback

    def update_callbacks(
        self,
        frame_callback: Optional[FrameCallback[FrameT]],
        queued_frames_callback: Optional[QueuedFramesCallback[FrameT]],
        ended_callback: Optional[MediaEndedCallback],
    ) -> None:
        with self._lock:
            self._frame_callback = frame_callback
            self._queued_frames_callback = queued_frames_callback
            self._media_ended_callback = ended_callback

    def recv(self, frame: FrameT) -> FrameT:
        with self._lock:
            if self._frame_callback:
                return self._frame_callback(frame)

        return frame

    async def recv_queued(self, frames: List[FrameT]) -> List[FrameT]:
        with self._lock:
            if self._queued_frames_callback:
                return await self._queued_frames_callback(frames)

        return [self.recv(frames[-1])]

    def on_ended(self):
        with self._lock:
            if self._media_ended_callback:
                return self._media_ended_callback()


class VideoProcessorBase(ProcessorBase[av.VideoFrame]):
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


class AudioProcessorBase(ProcessorBase[av.AudioFrame]):
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


VideoProcessorT = TypeVar(
    "VideoProcessorT",
    bound=Union[CallbackAttachableProcessor[av.VideoFrame], VideoProcessorBase],
)
AudioProcessorT = TypeVar(
    "AudioProcessorT",
    bound=Union[CallbackAttachableProcessor[av.AudioFrame], AudioProcessorBase],
)

MediaPlayerFactory = Callable[[], MediaPlayer]
MediaRecorderFactory = Callable[[], MediaRecorder]
VideoProcessorFactory = Callable[[], VideoProcessorT]
AudioProcessorFactory = Callable[[], AudioProcessorT]
ProcessorFactory = Union[VideoProcessorFactory, AudioProcessorFactory]

ProcessorT = TypeVar("ProcessorT", bound=Union[ProcessorBase, Any])
