import logging
import threading
import weakref
from typing import Callable, Union

from ._compat import AppSession, AppSessionState, get_script_run_ctx
from .session_info import get_this_session_info

logger = logging.getLogger(__name__)

Callback = Callable[[], None]


def _get_current_page_script_hash(app_session: AppSession) -> str:
    # AppSession updates `_client_state.page_script_hash` at SCRIPT_STARTED.
    # Streamlit's PagesManager mirrors it on `current_page_script_hash`, but
    # `_client_state` is the canonical source of truth on the session object.
    return getattr(app_session._client_state, "page_script_hash", "") or ""


class SessionShutdownObserver:
    """Watches the AppSession and runs ``callback`` when the resource it
    guards is no longer needed for this session.

    Two triggers, both polled on a background thread:

    - **Session shutdown**: ``AppSessionState.SHUTDOWN_REQUESTED`` (browser
      tab closed, server stop, etc.).
    - **Page navigation**: in a multi-page app, the user navigated away from
      the page where the resource was created. Without this, the worker /
      source track keeps running across page switches and the next visit
      collides with the stale instance.
    """

    _polling_thread: Union[threading.Thread, None]
    _polling_thread_stop_event: threading.Event
    _stop_lock: threading.Lock

    def __init__(self, callback: Callback) -> None:
        self._polling_thread = None
        self._polling_thread_stop_event = threading.Event()
        self._stop_lock = threading.Lock()
        self._callback = callback

        session_info = get_this_session_info()
        if session_info:
            session = session_info.session
            initial_page_script_hash = self._resolve_initial_page_script_hash(session)
            self._polling_thread = threading.Thread(
                target=self._polling_thread_impl,
                kwargs={
                    "app_session_ref": weakref.ref(session),
                    "initial_page_script_hash": initial_page_script_hash,
                },
                name=f"ShutdownPolling_{session.id}",
                daemon=True,
            )
            self._polling_thread.start()

    @staticmethod
    def _resolve_initial_page_script_hash(app_session: AppSession) -> str:
        # The observer is created during a script run, so prefer the live
        # ScriptRunContext — it reflects the page that is *currently*
        # executing, even if the AppSession's client_state hasn't been
        # updated yet for this run.
        ctx = get_script_run_ctx()
        if ctx is not None:
            page_hash = getattr(ctx, "page_script_hash", "") or ""
            if page_hash:
                return page_hash
        return _get_current_page_script_hash(app_session)

    def _polling_thread_impl(
        self,
        app_session_ref: "weakref.ReferenceType[AppSession]",
        initial_page_script_hash: str,
    ):
        navigated_away = False
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
            if initial_page_script_hash:
                current_page_script_hash = _get_current_page_script_hash(app_session)
                if (
                    current_page_script_hash
                    and current_page_script_hash != initial_page_script_hash
                ):
                    logger.debug(
                        "AppSession %s navigated from page %s to page %s, "
                        "stopping polling thread.",
                        app_session.id,
                        initial_page_script_hash,
                        current_page_script_hash,
                    )
                    navigated_away = True
                    break
            if self._polling_thread_stop_event.wait(1.0):
                logger.debug("Polling thread stop requested.")
                return

        # Ensure the flag is set
        self._polling_thread_stop_event.set()

        if navigated_away:
            logger.debug("Page navigation detected, executing callback.")
        else:
            logger.debug("AppSession shutdown detected, executing callback.")
        try:
            self._callback()
        except Exception as e:
            logger.exception("Error in shutdown callback: %s", e)

    def stop(self, timeout: float = 1.0) -> None:
        with self._stop_lock:
            polling_thread = self._polling_thread
            self._polling_thread = None
            self._polling_thread_stop_event.set()

        if polling_thread is None:
            return

        if threading.current_thread() is polling_thread:
            logger.debug("Stop called from polling thread itself, skipping join.")
            return

        polling_thread.join(timeout=timeout)
        if polling_thread.is_alive():
            logger.warning("ShutdownPolling thread did not exit cleanly")
        else:
            logger.debug("ShutdownPolling thread stopped cleanly")
