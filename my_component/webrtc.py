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

from aiortc_samples import VideoImageTrack, VideoTransformTrack


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
            recorder.addTrack(track) # TODO
        elif track.kind == "video":
            if player and player.video:
                pc.addTrack(player.video)
            else:
                local_video = VideoTransformTrack(
                    track, transform="edges"
                )
                # local_video = VideoImageTrack(track)
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
    def __init__(self, player_factory: Optional[MediaPlayerFactory]) -> None:
        self._thread = None
        self._loop = None
        self.pc = RTCPeerConnection()
        self._answer_queue = queue.Queue()
        self._stop_requested = False

        self.player_factory = player_factory

    def _run_webrtc_thread(
        self, sdp: str, type_: str, player_factory: Optional[MediaPlayerFactory]
    ):
        try:
            self._webrtc_thread(sdp=sdp, type_=type_, player_factory=player_factory)
        except Exception as e:
            logger.error("Error occurred in the WebRTC thread:")

            exc_type, exc_value, exc_traceback = sys.exc_info()
            for tb in traceback.format_exception(exc_type, exc_value, exc_traceback):
                for tbline in tb.rstrip().splitlines():
                    logger.error(tbline.rstrip())

            raise e

    def _webrtc_thread(
        self, sdp: str, type_: str, player_factory: Optional[MediaPlayerFactory]
    ):
        loop = asyncio.new_event_loop()
        self._loop = loop

        offer = RTCSessionDescription(sdp, type_)

        def callback(localDescription):
            self._answer_queue.put(localDescription)

        loop.create_task(process_offer(self.pc, offer, player_factory, callback))

        try:
            loop.run_forever()
        finally:
            loop.run_until_complete(self.pc.close())
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()

    def process_offer(self, sdp, type_, timeout=10.0):
        self._thread = threading.Thread(
            target=self._run_webrtc_thread,
            kwargs={"sdp": sdp, "type_": type_, "player_factory": self.player_factory},
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
