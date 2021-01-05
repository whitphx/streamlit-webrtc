import sys
import time
import threading
import logging
import traceback

logger = logging.getLogger(__name__)


class WebRtcThread:
    def __init__(self) -> None:
        self._thread = threading.Thread(target=self._run_webrtc_thread)
        self._stop_requested = False

        self._thread.start()

    def _run_webrtc_thread(self):
        try:
            self._webrtc_thread()
        except Exception:
            logger.error("Error occurred in the WebRTC thread:")

            exc_type, exc_value, exc_traceback = sys.exc_info()
            for tb in traceback.format_exception(exc_type, exc_value, exc_traceback):
                for tbline in tb.rstrip().splitlines():
                    logger.error(tbline.rstrip())

    def _webrtc_thread(self):
        while True:
            if self._stop_requested:
                break

            time.sleep(1)
            raise Exception("hoge")

    def stop(self):
        self._stop_requested = True
        self._thread.join(10)
        if self._thread.is_alive():
            logger.warning("The WebRTC thread has not been stopped.")
        self._thread = None


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
