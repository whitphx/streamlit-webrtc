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

        session_info = get_this_session_info()
        if session_info:
            session = session_info.session
            self._polling_thread = threading.Thread(
                target=self._polling_thread_impl,
                kwargs={
                    "app_session_ref": weakref.ref(session),
                    "callback": callback,
                },
                name=f"ShutdownPolling_{session.id}",
                daemon=True,
            )
            self._polling_thread.start()

    def _polling_thread_impl(
        self,
        app_session_ref: "weakref.ReferenceType[AppSession]",
        callback: Callback,
    ):
        # Use polling because event-based methods are not available
        # to observe the session lifecycle.
        while not self._polling_thread_stop_event.wait(1.0):
            app_session = app_session_ref()
            if not app_session:
                logger.debug("AppSession has removed.")
                break
            if app_session._state == AppSessionState.SHUTDOWN_REQUESTED:
                logger.debug(
                    "AppSession %s has been requested to shutdown.",
                    app_session.id,
                )
                break

        # Ensure the flag is set
        self._polling_thread_stop_event.set()

        logger.debug("AppSession shutdown has been detected.")
        callback()

    def stop(self):
        if self._polling_thread_stop_event.is_set():
            return

        if self._polling_thread:
            self._polling_thread_stop_event.set()
            self._polling_thread.join()
            self._polling_thread = None
