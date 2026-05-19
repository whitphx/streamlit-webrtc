import asyncio
import logging
from typing import Callable, Generic, Optional, Protocol, TypeVar, runtime_checkable

import av
from aiortc import MediaStreamTrack
from aiortc.mediastreams import MediaStreamError

logger = logging.getLogger(__name__)

FrameT = TypeVar("FrameT", av.VideoFrame, av.AudioFrame)


@runtime_checkable
class MediaSink(Protocol):
    """A consumer-side counterpart to a media source track.

    A ``MediaSink`` is attached to one input ``MediaStreamTrack`` via
    ``addTrack`` and pulled in a background task started by ``start``.
    Concrete implementations decide what to do with each frame —
    :class:`CallbackSinkTrack` dispatches to a user callback on the
    aiortc loop (no drop), while :class:`~streamlit_webrtc.receive.MediaReceiver`
    enqueues frames in a bounded queue for the Streamlit script thread to
    poll (drops on overflow). The streamer knows which kind a sink is for
    from the argument slot it was passed in (``sink_video_track`` vs
    ``sink_audio_track``), so the protocol does not require a ``kind``
    attribute.
    """

    def addTrack(self, track: MediaStreamTrack) -> None: ...
    def hasTrack(self) -> bool: ...
    def start(self) -> None: ...
    def stop(self) -> None: ...


SinkCallback = Callable[[FrameT], None]
VideoSinkCallback = SinkCallback[av.VideoFrame]
AudioSinkCallback = SinkCallback[av.AudioFrame]


class CallbackSinkTrack(Generic[FrameT]):
    """No-drop sink that dispatches each input frame to a user callback.

    The callback runs on aiortc's event loop. If the callback is slow it
    backpressures the read loop — every frame is delivered to the callback
    in order, with no intermediate bounded queue that could drop. Heavy
    work belongs in a worker thread the callback hands off to.
    """

    kind: str

    def __init__(
        self,
        callback: SinkCallback[FrameT],
        kind: str,
    ) -> None:
        self.kind = kind
        self._callback: SinkCallback[FrameT] = callback
        self._on_ended_callback: Optional[Callable[[], None]] = None
        self._track: Optional[MediaStreamTrack] = None
        self._task: Optional[asyncio.Task] = None

    def addTrack(self, track: MediaStreamTrack) -> None:
        # Recover after a prior session ended: a cached sink can be reused
        # for a new peer track once the previous run finished.
        if self._track is not None and self.readyState == "live":
            raise RuntimeError(f"{self} already has a live track {self._track}")
        self._track = track
        self._task = None

    def hasTrack(self) -> bool:
        return self._track is not None

    @property
    def readyState(self) -> str:
        if self._task is None:
            return "new"
        if self._task.done():
            return "ended"
        return "live"

    def start(self) -> None:
        if self._track is None:
            raise RuntimeError(f"{self} has no track attached")
        if self._task is not None and not self._task.done():
            raise RuntimeError(f"{self} has already a started task {self._task}")

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.get_event_loop_policy().get_event_loop()

        self._task = loop.create_task(self._run_track(self._track))

    def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self._task = None
        # Drop the reference so addTrack can rebind to a fresh peer track on a
        # subsequent session.
        self._track = None

    async def _run_track(self, track: MediaStreamTrack) -> None:
        try:
            while True:
                try:
                    frame = await track.recv()
                except MediaStreamError:
                    return
                try:
                    # aiortc's `track.recv()` is typed as `Frame | Packet`,
                    # but a kind-tagged sink only sees the matching frame.
                    self._callback(frame)  # type: ignore[arg-type]
                except Exception:
                    # Log and keep draining — the upstream track is fine, only
                    # user code failed. Mirrors the philosophy of the source
                    # tracks' callback error handling, but doesn't tear down
                    # the consumer for a transient bug in user code.
                    logger.exception(
                        "%s: sink callback raised an exception",
                        self.__class__.__name__,
                    )
        finally:
            self._fire_on_ended()

    def _fire_on_ended(self) -> None:
        cb = self._on_ended_callback
        if cb is None:
            return
        try:
            cb()
        except Exception:
            logger.exception(
                "%s: on_ended callback raised an exception",
                self.__class__.__name__,
            )


class VideoSinkTrack(CallbackSinkTrack[av.VideoFrame]):
    def __init__(self, callback: VideoSinkCallback) -> None:
        super().__init__(callback=callback, kind="video")


class AudioSinkTrack(CallbackSinkTrack[av.AudioFrame]):
    def __init__(self, callback: AudioSinkCallback) -> None:
        super().__init__(callback=callback, kind="audio")
