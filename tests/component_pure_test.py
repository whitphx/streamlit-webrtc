from typing import Any

import pytest

import streamlit_webrtc.component as component
from streamlit_webrtc.component import (
    ComponentValueSnapshot,
    WebRtcStreamerContext,
    WebRtcStreamerState,
    _handle_worker_lifecycle,
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
