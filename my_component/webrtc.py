import abc
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

from transform import VideoTransformerBase, NoOpVideoTransformer, VideoTransformTrack
from generate import VideoGeneratorBase, VideoImageTrack


VideoTransformFn = Callable

MediaPlayerFactory = Callable[..., MediaPlayer]


logger = logging.getLogger(__name__)


class WebRtcMode(enum.Enum):
    RECVONLY = enum.auto()
    SENDONLY = enum.auto()
    SENDRECV = enum.auto()


async def process_offer(
    pc: RTCPeerConnection,
    offer: RTCSessionDescription,
    player_factory: Optional[MediaPlayerFactory],
    video_transformer: Optional[VideoTransformerBase],
    video_generator: Optional[VideoGeneratorBase],
    callback: Callable[[], RTCSessionDescription],
):
    player = None
    if player_factory:
        player = player_factory()

    recorder = MediaBlackhole()

    @pc.on("iceconnectionstatechange")
    async def on_iceconnectionstatechange():
        print("ICE connection state is %s", pc.iceConnectionState)
        if pc.iceConnectionState == "failed":
            await pc.close()

    @pc.on("track")
    def on_track(track):
        print("Track %s received", track.kind)

        if track.kind == "audio":
            if player and player.audio:
                pc.addTrack(player.audio)
            recorder.addTrack(track)  # TODO
        elif track.kind == "video":
            if player and player.video:
                pc.addTrack(player.video)
            else:
                if video_transformer:
                    if video_generator:
                        print(
                            "Both video_transformer and video_generator are provided. video_transformer is used."
                        )
                    local_video = VideoTransformTrack(
                        track=track, video_transformer=video_transformer
                    )
                    pc.addTrack(local_video)
                elif video_generator:
                    local_video = VideoImageTrack(
                        track=track, video_generator=video_generator
                    )
                    pc.addTrack(local_video)

        @track.on("ended")
        async def on_ended():
            print("Track %s ended", track.kind)
            await recorder.stop()

    await pc.setRemoteDescription(offer)
    await recorder.start()

    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    callback(pc.localDescription)


class WebRtcWorker:
    def __init__(
        self,
        mode: WebRtcMode,
        player_factory: Optional[MediaPlayerFactory] = None,
        video_transformer_class: Optional[VideoTransformerBase] = None,
        video_generator_class: Optional[VideoGeneratorBase] = None,
    ) -> None:
        self._thread = None
        self._loop = None
        self.pc = RTCPeerConnection()
        self._answer_queue = queue.Queue()
        self._stop_requested = False

        self.mode = mode
        self.player_factory = player_factory
        self.video_transformer_class = video_transformer_class
        self.video_generator_class = video_generator_class

    def _run_webrtc_thread(
        self,
        sdp: str,
        type_: str,
        player_factory: Optional[MediaPlayerFactory],
        video_transformer_class: Optional[VideoTransformerBase],
        video_generator_class: Optional[VideoGeneratorBase],
    ):
        try:
            self._webrtc_thread(
                sdp=sdp,
                type_=type_,
                player_factory=player_factory,
                video_transformer_class=video_transformer_class,
                video_generator_class=video_generator_class,
            )
        except Exception as e:
            logger.error("Error occurred in the WebRTC thread:")

            exc_type, exc_value, exc_traceback = sys.exc_info()
            for tb in traceback.format_exception(exc_type, exc_value, exc_traceback):
                for tbline in tb.rstrip().splitlines():
                    logger.error(tbline.rstrip())

            raise e

    def _webrtc_thread(
        self,
        sdp: str,
        type_: str,
        player_factory: Optional[MediaPlayerFactory],
        video_transformer_class: Optional[VideoTransformerBase],
        video_generator_class: Optional[VideoGeneratorBase],
    ):
        loop = asyncio.new_event_loop()
        self._loop = loop

        offer = RTCSessionDescription(sdp, type_)

        def callback(localDescription):
            self._answer_queue.put(localDescription)

        video_transformer = None
        if video_transformer_class:
            video_transformer = video_transformer_class()
        video_generator = None
        if video_generator_class:
            video_generator = video_generator_class()

        if self.mode == WebRtcMode.SENDRECV:
            if video_transformer is None and video_generator is None:
                print(
                    "mode is set as sendrecv, but neither video_transformer_class nor video_generator_class are specified. A simple loopback transformer is used."
                )
                video_transformer = NoOpVideoTransformer()

        loop.create_task(
            process_offer(
                self.pc,
                offer,
                player_factory,
                video_transformer=video_transformer,
                video_generator=video_generator,
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
                "video_generator_class": self.video_generator_class,
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

    webrtc_worker = WebRtcWorker()
    localDescription = webrtc_worker.process_offer(offer.sdp, offer.type)

    logger.debug("localDescription:")
    logger.debug(localDescription)

    webrtc_worker.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    asyncio.run(test())
