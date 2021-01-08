import asyncio
import enum
import sys
import threading
import queue
import logging
import traceback
from typing import Callable, Optional

from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaBlackhole, MediaPlayer

from transform import (
    VideoTransformerBase,
    NoOpVideoTransformer,
    VideoTransformTrack,
    AsyncVideoTransformTrack,
)

logger = logging.getLogger(__name__)


VideoTransformFn = Callable

MediaPlayerFactory = Callable[..., MediaPlayer]


class WebRtcMode(enum.Enum):
    RECVONLY = enum.auto()
    SENDONLY = enum.auto()
    SENDRECV = enum.auto()


async def process_offer(
    mode: WebRtcMode,
    pc: RTCPeerConnection,
    offer: RTCSessionDescription,
    player_factory: Optional[MediaPlayerFactory],
    video_transformer: Optional[VideoTransformerBase],
    async_transform: bool,
    callback: Callable[[], RTCSessionDescription],
):
    player = None
    if player_factory:
        player = player_factory()

    recorder = MediaBlackhole()

    @pc.on("iceconnectionstatechange")
    async def on_iceconnectionstatechange():
        logger.info("ICE connection state is %s", pc.iceConnectionState)
        if pc.iceConnectionState == "failed":
            await pc.close()

    if mode == WebRtcMode.SENDRECV or mode == WebRtcMode.SENDONLY:

        @pc.on("track")
        def on_track(track):
            logger.info("Track %s received", track.kind)

            if track.kind == "audio":
                if player and player.audio:
                    pc.addTrack(player.audio)
                recorder.addTrack(track)  # TODO
            elif track.kind == "video":
                if player and player.video:
                    logger.info("Add player to video track")
                    pc.addTrack(player.video)
                elif video_transformer:
                    VideoTrack = (
                        AsyncVideoTransformTrack
                        if async_transform
                        else VideoTransformTrack
                    )
                    local_video = VideoTrack(
                        track=track, video_transformer=video_transformer
                    )
                    pc.addTrack(local_video)

            @track.on("ended")
            async def on_ended():
                logger.info("Track %s ended", track.kind)
                await recorder.stop()

    await pc.setRemoteDescription(offer)
    if mode == WebRtcMode.RECVONLY:
        for t in pc.getTransceivers():
            if t.kind == "audio":
                if player and player.audio:
                    pc.addTrack(player.audio)
            elif t.kind == "video":
                if player and player.video:
                    pc.addTrack(player.video)

    await recorder.start()  # TODO

    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    callback(pc.localDescription)


class WebRtcWorker:
    _video_transformer: Optional[VideoTransformerBase]

    @property
    def video_transformer(self) -> Optional[VideoTransformerBase]:
        return self._video_transformer

    def __init__(
        self,
        mode: WebRtcMode,
        player_factory: Optional[MediaPlayerFactory] = None,
        video_transformer_class: Optional[VideoTransformerBase] = None,
        async_transform: bool = True,
    ) -> None:
        self._thread = None
        self._loop = None
        self.pc = RTCPeerConnection()
        self._answer_queue = queue.Queue()
        self._stop_requested = False

        self.mode = mode
        self.player_factory = player_factory
        self.video_transformer_class = video_transformer_class
        self.async_transform = async_transform

        self._video_transformer = None

    def _run_webrtc_thread(
        self,
        sdp: str,
        type_: str,
        player_factory: Optional[MediaPlayerFactory],
        video_transformer_class: Optional[VideoTransformerBase],
        async_transform: bool,
    ):
        try:
            self._webrtc_thread(
                sdp=sdp,
                type_=type_,
                player_factory=player_factory,
                video_transformer_class=video_transformer_class,
                async_transform=async_transform,
            )
        except Exception as e:
            logger.error("Error occurred in the WebRTC thread:")

            exc_type, exc_value, exc_traceback = sys.exc_info()
            for tb in traceback.format_exception(exc_type, exc_value, exc_traceback):
                for tbline in tb.rstrip().splitlines():
                    logger.error(tbline.rstrip())

            # TODO shutdown this thread!
            raise e

    def _webrtc_thread(
        self,
        sdp: str,
        type_: str,
        player_factory: Optional[MediaPlayerFactory],
        video_transformer_class: Optional[VideoTransformerBase],
        async_transform: bool,
    ):
        logger.debug(
            "_webrtc_thread(player_factory=%s, video_transformer_class=%s)",
            player_factory,
            video_transformer_class,
        )

        loop = asyncio.new_event_loop()
        self._loop = loop

        offer = RTCSessionDescription(sdp, type_)

        def callback(localDescription):
            self._answer_queue.put(localDescription)

        video_transformer = None
        if video_transformer_class:
            video_transformer = video_transformer_class()

        if self.mode == WebRtcMode.SENDRECV:
            if video_transformer is None:
                logger.info(
                    "mode is set as sendrecv, but video_transformer_class is not specified. A simple loopback transformer is used."
                )
                video_transformer = NoOpVideoTransformer()

        self._video_transformer = video_transformer

        loop.create_task(
            process_offer(
                self.mode,
                self.pc,
                offer,
                player_factory,
                video_transformer=video_transformer,
                async_transform=async_transform,
                callback=callback,
            )
        )

        try:
            loop.run_forever()
        finally:
            loop.run_until_complete(self.pc.close())
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()

    def process_offer(self, sdp, type_, timeout=10.0):
        self._thread = threading.Thread(
            target=self._run_webrtc_thread,
            kwargs={
                "sdp": sdp,
                "type_": type_,
                "player_factory": self.player_factory,
                "video_transformer_class": self.video_transformer_class,
                "async_transform": self.async_transform,
            },
            daemon=True,
        )
        self._thread.start()

        answer = self._answer_queue.get(timeout)
        return answer

    def stop(self):
        if self._loop:
            self._loop.stop()
        if self._thread:
            self._thread.join()


async def test():
    client = RTCPeerConnection()
    client.createDataChannel("test")

    offer = await client.createOffer()

    webrtc_worker = WebRtcWorker(mode=WebRtcMode.SENDRECV)
    localDescription = webrtc_worker.process_offer(offer.sdp, offer.type)

    print("localDescription:")
    print(localDescription)

    webrtc_worker.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    asyncio.run(test())
