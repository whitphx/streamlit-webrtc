import logging
import threading
import weakref
from typing import Callable, Union

from streamlit.report_session import ReportSession, ReportSessionState

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
                    "report_session_ref": weakref.ref(session),
                    "callback": callback,
                },
                name=f"ShutdownPolling_{session.id}",
                daemon=True,
            )
            self._polling_thread.start()

    def _polling_thread_impl(
        self,
        report_session_ref: "weakref.ReferenceType[ReportSession]",
        callback: Callback,
    ):
        # Use polling because event-based methods are not available
        # to observe the session lifecycle.
        while not self._polling_thread_stop_event.wait(1.0):
            report_session = report_session_ref()
            if not report_session:
                logger.debug("ReportSession has removed.")
                break
            if report_session._state == ReportSessionState.SHUTDOWN_REQUESTED:
                logger.debug(
                    "ReportSession %s has been requested to shutdown.",
                    report_session.id,
                )
                break

        # Ensure the flag is set
        self._polling_thread_stop_event.set()

        logger.debug("ReportSession shutdown has been detected.")
        callback()

    def stop(self):
        if self._polling_thread_stop_event.is_set():
            return

        if self._polling_thread:
            self._polling_thread_stop_event.set()
            self._polling_thread.join()
            self._polling_thread = None
