from unittest.mock import MagicMock

import pytest

from streamlit_webrtc.component import (
    WebRtcStreamerContext,
    WebRtcStreamerState,
    _handle_frontend_event,
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


class TestHandleFrontendEvent:
    def test_stops_worker_and_clears_pending_answer(self) -> None:
        worker = MagicMock()
        context: WebRtcStreamerContext = WebRtcStreamerContext(
            worker=worker,
            state=WebRtcStreamerState(playing=True, signalling=False),
        )
        context._sdp_answer_json = '{"type":"answer","sdp":"v=0\\r\\n"}'
        context._is_sdp_answer_sent = True

        _handle_frontend_event(
            context,
            "key",
            {
                "frontendEvent": {
                    "id": "event-1",
                    "type": "connection_lost",
                    "reason": "pc.connectionState=failed",
                }
            },
        )

        worker.stop.assert_called_once()
        assert context._get_worker() is None
        assert context._sdp_answer_json is None
        assert context._is_sdp_answer_sent is False
        assert context._last_frontend_event_id == "event-1"

    def test_ignores_duplicate_event(self) -> None:
        worker = MagicMock()
        context: WebRtcStreamerContext = WebRtcStreamerContext(
            worker=worker,
            state=WebRtcStreamerState(playing=True, signalling=False),
        )
        component_value = {
            "frontendEvent": {
                "id": "event-1",
                "type": "connection_lost",
                "reason": "pc.connectionState=failed",
            }
        }

        _handle_frontend_event(context, "key", component_value)
        context._set_worker(worker)
        _handle_frontend_event(context, "key", component_value)

        worker.stop.assert_called_once()
