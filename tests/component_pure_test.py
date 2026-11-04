import threading
import time
from types import SimpleNamespace
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest
import streamlit as st

import streamlit_webrtc.component as component
from streamlit_webrtc.component import (
    ComponentValueSnapshot,
    WebRtcStreamerContext,
    WebRtcStreamerState,
    _handle_worker_lifecycle,
    _make_state_change_callback,
    _validate_sink_conflicts,
    compile_state,
    generate_frontend_component_key,
)
from streamlit_webrtc.sink import VideoSinkTrack


class TestCompileState:
    def test_neither_playing_nor_signalling(self) -> None:
        state = compile_state({})
        assert state.playing is False
        assert state.signalling is False

    def test_playing_only(self) -> None:
        state = compile_state({"playing": True})
        assert state.playing is True
        assert state.signalling is False

    def test_signalling_derived_from_sdp_offer_truthiness(self) -> None:
        # An empty dict is falsy -> not signalling.
        assert compile_state({"sdpOffer": {}}).signalling is False
        # A populated dict is truthy -> signalling.
        assert (
            compile_state({"sdpOffer": {"sdp": "v=0\r\n", "type": "offer"}}).signalling
            is True
        )

    def test_both_true(self) -> None:
        state = compile_state(
            {"playing": True, "sdpOffer": {"sdp": "v=0\r\n", "type": "offer"}}
        )
        assert state.playing is True
        assert state.signalling is True


class TestGenerateFrontendComponentKey:
    def test_idempotent(self) -> None:
        # Same input -> same output, every time.
        assert generate_frontend_component_key("k") == generate_frontend_component_key(
            "k"
        )

    def test_distinct_keys_stay_distinct(self) -> None:
        assert generate_frontend_component_key("a") != generate_frontend_component_key(
            "b"
        )

    def test_output_contains_original_key(self) -> None:
        # The frontend key is a prefix + salt; the prefix is the user-supplied
        # key. Anything that strips that property would break Streamlit's
        # session-state correlation between the Python and frontend sides.
        assert generate_frontend_component_key("my-key").startswith("my-key")

    def test_collision_resistant_under_simple_substring_attack(self) -> None:
        # The salt prevents `key="x:frontend"` from colliding with the frontend
        # key generated from `key="x"`. Without the salt, an attacker (or a
        # careless user) picking that suffix could shadow another widget.
        assert generate_frontend_component_key(
            "x:frontend"
        ) != generate_frontend_component_key("x")


class TestHandleWorkerLifecycle:
    def test_idle_stale_sdp_answer_resets_context_and_reruns(self, monkeypatch) -> None:
        reruns: list[bool] = []
        monkeypatch.setattr(component, "rerun", lambda: reruns.append(True))
        context: WebRtcStreamerContext[Any, Any] = WebRtcStreamerContext(
            worker=None, state=WebRtcStreamerState(playing=False, signalling=False)
        )
        context._sdp_answer_json = '{"sdp":"v=0\\r\\n","type":"answer"}'
        context._is_sdp_answer_sent = True
        context._component_value_snapshot = ComponentValueSnapshot(
            component_value={"playing": False}, run_count=1
        )

        _handle_worker_lifecycle(
            context,
            key="k",
            sdp_offer=None,
            make_worker=lambda: pytest.fail("worker should not be created"),
        )

        assert context._get_worker() is None
        assert context.state == WebRtcStreamerState(playing=False, signalling=False)
        assert context._sdp_answer_json is None
        assert context._is_sdp_answer_sent is False
        assert context._component_value_snapshot is None
        assert reruns == [True]

    def test_idle_without_worker_or_stale_sdp_does_not_rerun(self, monkeypatch) -> None:
        reruns: list[bool] = []
        monkeypatch.setattr(component, "rerun", lambda: reruns.append(True))
        context: WebRtcStreamerContext[Any, Any] = WebRtcStreamerContext(
            worker=None, state=WebRtcStreamerState(playing=False, signalling=False)
        )

        _handle_worker_lifecycle(
            context,
            key="k",
            sdp_offer=None,
            make_worker=lambda: pytest.fail("worker should not be created"),
        )

        assert reruns == []

    @pytest.mark.parametrize(
        "frontend_sdp_offer_after", ["", {"sdp": "second offer", "type": "offer"}]
    )
    def test_worker_for_an_offer_left_during_its_creation_is_stopped(
        self, monkeypatch, frontend_sdp_offer_after
    ) -> None:
        reruns: list[bool] = []
        monkeypatch.setattr(component, "rerun", lambda: reruns.append(True))
        offer = {"sdp": "first offer", "type": "offer"}
        context: WebRtcStreamerContext[Any, Any] = WebRtcStreamerContext(
            worker=None, state=WebRtcStreamerState(playing=False, signalling=True)
        )
        context._frontend_sdp_offer = offer
        worker = MagicMock()
        worker.local_description = SimpleNamespace(sdp="first answer", type="answer")

        def leave_offer(*args, **kwargs) -> None:
            context._frontend_sdp_offer = frontend_sdp_offer_after

        worker.process_offer.side_effect = leave_offer

        _handle_worker_lifecycle(
            context, key="k", sdp_offer=offer, make_worker=lambda: worker
        )

        worker.stop.assert_called_once()
        assert context._get_worker() is None
        assert context._sdp_answer_json is None
        assert reruns == []

    def test_run_holding_an_offer_the_frontend_left_creates_no_worker(self) -> None:
        context: WebRtcStreamerContext[Any, Any] = WebRtcStreamerContext(
            worker=None, state=WebRtcStreamerState(playing=False, signalling=True)
        )
        context._frontend_sdp_offer = {"sdp": "second offer", "type": "offer"}

        _handle_worker_lifecycle(
            context,
            key="k",
            sdp_offer={"sdp": "first offer", "type": "offer"},
            make_worker=lambda: pytest.fail("worker should not be created"),
        )

        assert context._get_worker() is None


class TestStateChangeCallback:
    def test_new_offer_discards_the_previous_offers_worker_and_answer(self) -> None:
        key = "state-change-callback"
        frontend_key = generate_frontend_component_key(key)
        context: WebRtcStreamerContext[Any, Any] = WebRtcStreamerContext(
            worker=None, state=WebRtcStreamerState(playing=True, signalling=False)
        )
        worker = MagicMock()
        context._set_worker(worker)
        context._worker_sdp_offer = {"sdp": "first offer", "type": "offer"}
        context._sdp_answer_json = '{"sdp":"first answer","type":"answer"}'
        context._is_sdp_answer_sent = True
        st.session_state[key] = context
        # STOP and START again with no script run in between.
        st.session_state[frontend_key] = {
            "playing": False,
            "sdpOffer": {"sdp": "second offer", "type": "offer"},
            "iceCandidates": {},
        }
        try:
            _make_state_change_callback(key, frontend_key, None)()
        finally:
            del st.session_state[key]
            del st.session_state[frontend_key]

        worker.stop.assert_called_once()
        assert context._get_worker() is None
        assert context._sdp_answer_json is None
        assert context._is_sdp_answer_sent is False
        assert context.state == WebRtcStreamerState(playing=False, signalling=True)


class _ContentionSignallingLock:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.contended = threading.Event()

    def __enter__(self) -> None:
        if not self._lock.acquire(blocking=False):
            self.contended.set()
            self._lock.acquire()

    def __exit__(self, *exc_info: object) -> None:
        self._lock.release()


class TestNegotiationRace:
    """A newer offer's state-change callback runs on another thread while a
    superseded run is attaching its worker or flushing its answer."""

    key = "negotiation-race"
    first_offer = {"sdp": "first offer", "type": "offer"}
    second_offer = {"sdp": "second offer", "type": "offer"}

    @pytest.fixture
    def context(self, monkeypatch):
        monkeypatch.setattr(component, "rerun", lambda: None)
        context: WebRtcStreamerContext[Any, Any] = WebRtcStreamerContext(
            worker=None, state=WebRtcStreamerState(playing=False, signalling=True)
        )
        context._frontend_sdp_offer = self.first_offer
        context._negotiation_lock = _ContentionSignallingLock()  # type: ignore[assignment]
        st.session_state[self.key] = context
        yield context
        del st.session_state[self.key]
        del st.session_state[generate_frontend_component_key(self.key)]

    def _report_offer_concurrently(
        self, context: WebRtcStreamerContext, sdp_offer: Dict
    ) -> threading.Thread:
        """Run the callback for `sdp_offer` on another thread, and return once
        it has finished or is waiting for the negotiation lock."""
        frontend_key = generate_frontend_component_key(self.key)
        st.session_state[frontend_key] = {"playing": False, "sdpOffer": sdp_offer}
        thread = threading.Thread(
            target=_make_state_change_callback(self.key, frontend_key, None)
        )
        thread.start()
        lock = context._negotiation_lock
        assert isinstance(lock, _ContentionSignallingLock)
        deadline = time.monotonic() + 5
        while thread.is_alive() and not lock.contended.wait(0.01):
            assert time.monotonic() < deadline
        return thread

    def test_new_offer_during_worker_attach_discards_the_worker(self, context) -> None:
        worker = MagicMock()
        worker.local_description = None
        set_worker = context._set_worker
        threads: list[threading.Thread] = []

        def set_worker_then_report_new_offer(new_worker) -> None:
            set_worker(new_worker)
            if new_worker is worker and not threads:
                threads.append(
                    self._report_offer_concurrently(context, self.second_offer)
                )

        context._set_worker = set_worker_then_report_new_offer

        _handle_worker_lifecycle(
            context,
            key=self.key,
            sdp_offer=self.first_offer,
            make_worker=lambda: worker,
        )
        threads[0].join()

        worker.stop.assert_called_once()
        assert context._get_worker() is None

    def test_new_offer_during_answer_flush_drops_the_answer(self, context) -> None:
        worker = MagicMock()
        context._set_worker(worker)
        context._worker_sdp_offer = self.first_offer
        threads: list[threading.Thread] = []

        def answer_then_report_new_offer() -> SimpleNamespace:
            if not threads:
                threads.append(
                    self._report_offer_concurrently(context, self.second_offer)
                )
            return SimpleNamespace(sdp="first answer", type="answer")

        type(worker).local_description = property(
            lambda self: answer_then_report_new_offer()
        )

        _handle_worker_lifecycle(
            context, key=self.key, sdp_offer=self.first_offer, make_worker=pytest.fail
        )
        threads[0].join()

        worker.stop.assert_called_once()
        assert context._get_worker() is None
        assert context._sdp_answer_json is None


class TestValidateSinkConflicts:
    def _sink(self) -> VideoSinkTrack:
        return VideoSinkTrack(callback=lambda frame: None)

    def test_no_sink_is_a_noop(self) -> None:
        # Without a sink, every other arg is allowed.
        _validate_sink_conflicts(
            kind="video",
            sink=None,
            frame_callback=lambda f: f,
            queued_frames_callback=None,
            on_ended=None,
            processor_factory=lambda: object(),
        )

    def test_sink_alone_is_allowed(self) -> None:
        _validate_sink_conflicts(
            kind="video",
            sink=self._sink(),
            frame_callback=None,
            queued_frames_callback=None,
            on_ended=None,
            processor_factory=None,
        )

    def test_sink_plus_frame_callback_rejected(self) -> None:
        with pytest.raises(ValueError, match="video_frame_callback"):
            _validate_sink_conflicts(
                kind="video",
                sink=self._sink(),
                frame_callback=lambda f: f,
                queued_frames_callback=None,
                on_ended=None,
                processor_factory=None,
            )

    def test_sink_plus_queued_frames_callback_rejected(self) -> None:
        async def queued(frames):
            return frames

        with pytest.raises(ValueError, match="queued_video_frames_callback"):
            _validate_sink_conflicts(
                kind="video",
                sink=self._sink(),
                frame_callback=None,
                queued_frames_callback=queued,
                on_ended=None,
                processor_factory=None,
            )

    def test_sink_plus_on_ended_rejected(self) -> None:
        with pytest.raises(ValueError, match="on_video_ended"):
            _validate_sink_conflicts(
                kind="video",
                sink=self._sink(),
                frame_callback=None,
                queued_frames_callback=None,
                on_ended=lambda: None,
                processor_factory=None,
            )

    def test_sink_plus_processor_factory_rejected(self) -> None:
        with pytest.raises(ValueError, match="video_processor_factory"):
            _validate_sink_conflicts(
                kind="video",
                sink=self._sink(),
                frame_callback=None,
                queued_frames_callback=None,
                on_ended=None,
                processor_factory=lambda: object(),
            )
