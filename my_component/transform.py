import abc

from aiortc import MediaStreamTrack

from av import VideoFrame


class VideoTransformerBase(abc.ABC):
    @abc.abstractmethod
    def transform(self, frame: VideoFrame) -> VideoFrame:
        """ Returns a new VideoFrame """


class NoOpVideoTransformer(VideoTransformerBase):
    def transform(self, frame: VideoFrame) -> VideoFrame:
        return frame


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
        return self.transformer.transform(frame)
