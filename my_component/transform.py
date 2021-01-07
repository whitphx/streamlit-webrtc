import abc

from aiortc import MediaStreamTrack

import numpy as np
from av import VideoFrame


class VideoTransformerBase(abc.ABC):
    @abc.abstractmethod
    def transform(self, frame_bgr24: np.ndarray) -> np.ndarray:
        """ Returns a BGR24 image """


class NoOpVideoTransformer(VideoTransformerBase):
    def transform(self, frame_bgr24: np.ndarray) -> np.ndarray:
        return frame_bgr24


class VideoTransformTrack(MediaStreamTrack):
    kind = "video"

    def __init__(
        self, track: MediaStreamTrack, video_transformer: VideoTransformerBase
    ):
        super().__init__()  # don't forget this!
        self.track = track
        self.transformer = video_transformer

    async def recv(self):
        frame = await self.track.recv()
        img = frame.to_ndarray(format="bgr24")
        transformed_img = self.transformer.transform(img)

        new_frame = VideoFrame.from_ndarray(transformed_img, format="bgr24")
        new_frame.pts = frame.pts
        new_frame.time_base = frame.time_base
        return new_frame
