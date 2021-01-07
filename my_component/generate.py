import abc
import fractions

from aiortc import VideoStreamTrack

import numpy as np
from av import VideoFrame


class VideoGeneratorBase(abc.ABC):
    @abc.abstractmethod
    def generate(self, pts: int, time_base: fractions.Fraction) -> np.ndarray:
        """ Returns a BGR24 image """


class VideoImageTrack(VideoStreamTrack):
    def __init__(self, track, video_generator: VideoGeneratorBase):
        super().__init__()
        self.track = track
        self.generator = video_generator

    async def recv(self):
        pts, time_base = await self.next_timestamp()

        img = self.generator.generate(pts, time_base)

        frame = VideoFrame.from_ndarray(img, format="bgr24")
        frame.pts = pts
        frame.time_base = time_base

        return frame
