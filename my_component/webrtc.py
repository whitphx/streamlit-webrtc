import asyncio
import sys
import threading
import queue
import logging
import traceback

from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaPlayer


logger = logging.getLogger(__name__)


async def process_offer(pc, offer, callback):
    @pc.on("iceconnectionstatechange")
    async def on_iceconnectionstatechange():
        if pc.iceConnectionState == "failed":
            await pc.close()

    # Open media source
    # TODO: Be configurable
    # player = MediaPlayer("./sample-mp4-file.mp4")
    player = MediaPlayer(
        "1:none",
        format="avfoundation",
        options={"framerate": "30", "video_size": "1280x720"},
    )

    await pc.setRemoteDescription(offer)
    for t in pc.getTransceivers():
        if t.kind == "audio" and player.audio:
            pc.addTrack(player.audio)
        elif t.kind == "video" and player.video:
            pc.addTrack(player.video)

    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    callback(pc.localDescription)


class WebRtcWorker:
    def __init__(self) -> None:
        self._thread = None
        self._loop = None
        self.pc = RTCPeerConnection()
        self._answer_queue = queue.Queue()
        self._stop_requested = False

    def _run_webrtc_thread(self, sdp, type_):
        try:
            self._webrtc_thread(sdp=sdp, type_=type_)
        except Exception:
            logger.error("Error occurred in the WebRTC thread:")

            exc_type, exc_value, exc_traceback = sys.exc_info()
            for tb in traceback.format_exception(exc_type, exc_value, exc_traceback):
                for tbline in tb.rstrip().splitlines():
                    logger.error(tbline.rstrip())

    def _webrtc_thread(self, sdp, type_):
        loop = asyncio.new_event_loop()
        self._loop = loop

        offer = RTCSessionDescription(sdp, type_)

        def callback(localDescription):
            self._answer_queue.put(localDescription)

        loop.create_task(process_offer(self.pc, offer, callback))

        try:
            loop.run_forever()
        finally:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()

    def process_offer(self, sdp, type_, timeout=10.0):
        self._thread = threading.Thread(
            target=self._run_webrtc_thread, kwargs={"sdp": sdp, "type_": type_}
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
