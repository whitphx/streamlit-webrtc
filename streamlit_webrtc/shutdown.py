import logging
import threading
import weakref
from typing import Callable, Union

from ._compat import AppSession, AppSessionState
from .session_info import get_this_session_info

logger = logging.getLogger(__name__)

Callback = Callable[[], None]


class SessionShutdownObserver:
    _polling_thread: Union[threading.Thread, None]
    _polling_thread_stop_event: threading.Event

    def __init__(self, callback: Callback) -> None:
        self._polling_thread = None
        self._polling_thread_stop_event = threading.Event()
        self._callback = callback

        session_info = get_this_session_info()
        if session_info:
            session = session_info.session
            self._polling_thread = threading.Thread(
                target=self._polling_thread_impl,
                kwargs={
                    "app_session_ref": weakref.ref(session),
                },
                name=f"ShutdownPolling_{session.id}",
                daemon=True,
            )
            self._polling_thread.start()

    def _polling_thread_impl(
        self,
        app_session_ref: "weakref.ReferenceType[AppSession]",
    ):
        while True:
            app_session = app_session_ref()
            if not app_session:
                logger.debug("AppSession removed, stopping polling thread.")
                break
            if app_session._state == AppSessionState.SHUTDOWN_REQUESTED:
                logger.debug(
                    "AppSession %s requested shutdown, stopping polling thread.",
                    app_session.id,
                )
                break
            if self._polling_thread_stop_event.wait(1.0):
                logger.debug("Polling thread stop requested.")
                return

        # Ensure the flag is set
        self._polling_thread_stop_event.set()

        logger.debug("AppSession shutdown detected, executing callback.")
        try:
            self._callback()
        except Exception as e:
            logger.exception("Error in shutdown callback: %s", e)

    def stop(self, timeout: float = 1.0) -> None:
        if self._polling_thread:
            self._polling_thread_stop_event.set()

            # 🔑 FIX: do not join current thread
            if threading.current_thread() is not self._polling_thread:
                self._polling_thread.join(timeout=timeout)
                if self._polling_thread.is_alive():
                    logger.warning("ShutdownPolling thread did not exit cleanly")
                else:
                    logger.debug("ShutdownPolling thread stopped cleanly")
            else:
                logger.debug("Stop called from polling thread itself, skipping join.")

            self._polling_thread = None
