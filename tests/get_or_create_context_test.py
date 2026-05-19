"""Tests for `_get_or_create_context`'s orphaned-context detection.

The detection is what makes a same-tick page-away-and-back round-trip safe
in a multi-page app: the SessionShutdownObserver's polling thread fires
within ~1s of navigation, but the user can return faster than that and a
stale worker/state must not be re-used against the freshly mounted iframe.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import streamlit as st

from streamlit_webrtc.component import (
    WebRtcStreamerContext,
    WebRtcStreamerState,
    _get_or_create_context,
)


def _patches(session_info):
    """Patch the session_info / script_run_count lookups together so each
    test only juggles two return values."""
    return (
        patch(
            "streamlit_webrtc.component.get_this_session_info",
            return_value=session_info,
        ),
        patch(
            "streamlit_webrtc.component.get_script_run_count",
            side_effect=lambda info: info.script_run_count,
        ),
    )


def test_no_session_info_skips_run_count_tracking():
    # In test / non-Streamlit contexts, `get_this_session_info()` returns
    # None and the orphan-detection logic must no-op rather than crash.
    if "key1" in st.session_state:
        del st.session_state["key1"]
    with patch("streamlit_webrtc.component.get_this_session_info", return_value=None):
        ctx = _get_or_create_context("key1")
    assert isinstance(ctx, WebRtcStreamerContext)
    assert ctx._last_rendered_run_count is None


def test_consecutive_renders_do_not_trigger_reset():
    if "key2" in st.session_state:
        del st.session_state["key2"]
    info = SimpleNamespace(script_run_count=5)
    session_info_patch, run_count_patch = _patches(info)
    with session_info_patch, run_count_patch:
        ctx = _get_or_create_context("key2")
        assert ctx._last_rendered_run_count == 5

        # Simulate the user clicking Start: worker exists, state goes
        # playing. The script reruns once more (count = 6).
        worker = MagicMock()
        ctx._set_worker(worker)
        ctx._set_state(WebRtcStreamerState(playing=True, signalling=False))
        ctx._sdp_answer_json = "stub-answer"
        ctx._is_sdp_answer_sent = True

        info.script_run_count = 6
        ctx2 = _get_or_create_context("key2")

    assert ctx2 is ctx
    # Worker and playing-state preserved across a normal consecutive render.
    assert ctx2._get_worker() is worker
    assert ctx2.state.playing is True
    worker.stop.assert_not_called()


def test_orphaned_context_resets_worker_and_state():
    # Simulates page-A → page-B → page-A. The polling thread didn't get a
    # chance to fire (or fired but the context still carries stale state),
    # so `_get_or_create_context` must detect the gap and reset.
    if "key3" in st.session_state:
        del st.session_state["key3"]

    info = SimpleNamespace(script_run_count=10)
    session_info_patch, run_count_patch = _patches(info)
    with session_info_patch, run_count_patch:
        ctx = _get_or_create_context("key3")
        assert ctx._last_rendered_run_count == 10

        worker = MagicMock()
        ctx._set_worker(worker)
        ctx._set_state(WebRtcStreamerState(playing=True, signalling=False))
        ctx._sdp_answer_json = "stub-answer"
        ctx._is_sdp_answer_sent = True

        # User navigated away (count advanced beyond +1) and is back.
        info.script_run_count = 12
        ctx2 = _get_or_create_context("key3")

    assert ctx2 is ctx
    worker.stop.assert_called_once()
    assert ctx2._get_worker() is None
    assert ctx2.state == WebRtcStreamerState(playing=False, signalling=False)
    assert ctx2._sdp_answer_json is None
    assert ctx2._is_sdp_answer_sent is False
    assert ctx2._last_rendered_run_count == 12


def test_orphan_reset_handles_already_stopped_worker():
    # Same scenario as above, but the SessionShutdownObserver's polling
    # thread already called worker.stop() before the user returned. The
    # context still holds a weakref-resolvable worker reference, so the
    # reset path must tolerate `.stop()` being called twice without
    # blowing up.
    if "key4" in st.session_state:
        del st.session_state["key4"]

    info = SimpleNamespace(script_run_count=1)
    session_info_patch, run_count_patch = _patches(info)
    with session_info_patch, run_count_patch:
        ctx = _get_or_create_context("key4")

        worker = MagicMock()
        ctx._set_worker(worker)

        info.script_run_count = 5
        _get_or_create_context("key4")

    worker.stop.assert_called_once()
