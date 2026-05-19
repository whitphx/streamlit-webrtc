import threading
from types import SimpleNamespace
from unittest.mock import patch

from streamlit_webrtc._compat import AppSessionState
from streamlit_webrtc.shutdown import SessionShutdownObserver


class _FakeClientState:
    def __init__(self, page_script_hash: str) -> None:
        self.page_script_hash = page_script_hash


class _FakeAppSession:
    """Stand-in for `streamlit.runtime.app_session.AppSession`.

    Defined as a regular class (not SimpleNamespace) so it can be the target
    of `weakref.ref`, matching the real AppSession's GC story.
    """

    def __init__(self, page_hash: str, state=None) -> None:
        self.id = "sess-1"
        self._state = state if state is not None else AppSessionState.APP_IS_RUNNING
        self._client_state = _FakeClientState(page_hash)


def _make_session_info(session):
    return SimpleNamespace(session=session)


def test_no_session_info_does_not_start_polling_thread():
    callback_called = threading.Event()
    with patch("streamlit_webrtc.shutdown.get_this_session_info", return_value=None):
        observer = SessionShutdownObserver(callback_called.set)
    try:
        # No session -> no polling thread, no callback ever fires
        assert observer._polling_thread is None
        assert not callback_called.wait(0.2)
    finally:
        observer.stop()


def test_callback_fires_on_session_shutdown():
    session = _FakeAppSession(page_hash="page-A")
    callback_called = threading.Event()
    with (
        patch(
            "streamlit_webrtc.shutdown.get_this_session_info",
            return_value=_make_session_info(session),
        ),
        patch("streamlit_webrtc.shutdown.get_script_run_ctx", return_value=None),
    ):
        observer = SessionShutdownObserver(callback_called.set)
    try:
        session._state = AppSessionState.SHUTDOWN_REQUESTED
        assert callback_called.wait(3.0)
    finally:
        observer.stop()


def test_callback_fires_on_page_navigation():
    session = _FakeAppSession(page_hash="page-A")
    callback_called = threading.Event()
    with (
        patch(
            "streamlit_webrtc.shutdown.get_this_session_info",
            return_value=_make_session_info(session),
        ),
        patch("streamlit_webrtc.shutdown.get_script_run_ctx", return_value=None),
    ):
        observer = SessionShutdownObserver(callback_called.set)
    try:
        # Simulate the user navigating to a different page
        session._client_state.page_script_hash = "page-B"
        assert callback_called.wait(3.0)
    finally:
        observer.stop()


def test_callback_does_not_fire_when_page_hash_unchanged():
    session = _FakeAppSession(page_hash="page-A")
    callback_called = threading.Event()
    with (
        patch(
            "streamlit_webrtc.shutdown.get_this_session_info",
            return_value=_make_session_info(session),
        ),
        patch("streamlit_webrtc.shutdown.get_script_run_ctx", return_value=None),
    ):
        observer = SessionShutdownObserver(callback_called.set)
    try:
        # Reassigning the same hash should not fire the callback
        session._client_state.page_script_hash = "page-A"
        assert not callback_called.wait(1.5)
    finally:
        observer.stop()


def test_initial_page_hash_taken_from_script_run_ctx_when_available():
    # The ScriptRunCtx is the canonical source for "what page is this script
    # running for"; the observer should prefer it over the AppSession's
    # client_state, which is updated by a separate code path.
    session = _FakeAppSession(page_hash="page-A")
    ctx = SimpleNamespace(page_script_hash="page-A")
    callback_called = threading.Event()
    with (
        patch(
            "streamlit_webrtc.shutdown.get_this_session_info",
            return_value=_make_session_info(session),
        ),
        patch("streamlit_webrtc.shutdown.get_script_run_ctx", return_value=ctx),
    ):
        observer = SessionShutdownObserver(callback_called.set)
    try:
        assert not callback_called.wait(1.5)
        # Navigating away triggers the callback.
        session._client_state.page_script_hash = "page-B"
        assert callback_called.wait(3.0)
    finally:
        observer.stop()


def test_no_initial_page_hash_does_not_fire_on_page_change():
    # When the observer cannot determine an initial page hash (neither the
    # ScriptRunCtx nor the session expose one — e.g., the observer is built
    # from a worker thread that has no live Streamlit context), the
    # page-change branch must remain dormant. Only the shutdown trigger
    # should remain in effect.
    session = _FakeAppSession(page_hash="")
    callback_called = threading.Event()
    with (
        patch(
            "streamlit_webrtc.shutdown.get_this_session_info",
            return_value=_make_session_info(session),
        ),
        patch("streamlit_webrtc.shutdown.get_script_run_ctx", return_value=None),
    ):
        observer = SessionShutdownObserver(callback_called.set)
    try:
        session._client_state.page_script_hash = "page-B"
        assert not callback_called.wait(1.5)
        session._state = AppSessionState.SHUTDOWN_REQUESTED
        assert callback_called.wait(3.0)
    finally:
        observer.stop()


def test_stop_idempotent_and_safe_to_call_after_callback():
    session = _FakeAppSession(page_hash="page-A")
    callback_called = threading.Event()
    with (
        patch(
            "streamlit_webrtc.shutdown.get_this_session_info",
            return_value=_make_session_info(session),
        ),
        patch("streamlit_webrtc.shutdown.get_script_run_ctx", return_value=None),
    ):
        observer = SessionShutdownObserver(callback_called.set)
    try:
        session._state = AppSessionState.SHUTDOWN_REQUESTED
        assert callback_called.wait(3.0)
    finally:
        # Calling stop() after the callback already ran must not raise.
        observer.stop()
        # Idempotent.
        observer.stop()
