import pytest

from streamlit_webrtc.component import (
    _WEBRTC_STREAMER_OPTION_NAMES,
    _normalize_webrtc_streamer_options,
    _validate_sink_conflicts,
    compile_state,
    generate_frontend_component_key,
)
from streamlit_webrtc.sink import VideoSinkTrack
from streamlit_webrtc.webrtc import WebRtcMode


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


class TestNormalizeWebRtcStreamerOptions:
    def test_keyword_options_overlay_defaults(self) -> None:
        options = _normalize_webrtc_streamer_options(
            (),
            {"mode": WebRtcMode.SENDONLY, "media_toggle_controls": False},
        )

        assert options["mode"] is WebRtcMode.SENDONLY
        assert options["media_toggle_controls"] is False
        assert options["async_processing"] is True

    def test_legacy_positional_options_are_mapped_with_warning(self) -> None:
        with pytest.warns(DeprecationWarning, match="keyword arguments"):
            options = _normalize_webrtc_streamer_options(
                (WebRtcMode.RECVONLY, {"iceServers": []}),
                {},
            )

        assert options["mode"] is WebRtcMode.RECVONLY
        assert options["rtc_configuration"] == {"iceServers": []}

    def test_legacy_tail_positionals_keep_their_slots(self) -> None:
        def on_change() -> None:
            pass

        def video_transformer_factory() -> object:
            return object()

        on_change_index = _WEBRTC_STREAMER_OPTION_NAMES.index("on_change")
        args = (None,) * on_change_index + (
            on_change,
            video_transformer_factory,
            False,
            False,
        )

        with pytest.warns(DeprecationWarning, match="keyword arguments"):
            options = _normalize_webrtc_streamer_options(args, {})

        assert options["on_change"] is on_change
        assert options["video_transformer_factory"] is video_transformer_factory
        assert options["async_transform"] is False
        assert options["media_toggle_controls"] is False

    def test_duplicate_positional_and_keyword_option_is_rejected(self) -> None:
        with pytest.raises(TypeError, match="multiple values.*mode"):
            _normalize_webrtc_streamer_options(
                (WebRtcMode.SENDONLY,),
                {"mode": WebRtcMode.RECVONLY},
            )

    def test_unknown_keyword_option_is_rejected(self) -> None:
        with pytest.raises(TypeError, match="unexpected keyword argument 'unknown'"):
            _normalize_webrtc_streamer_options((), {"unknown": object()})

    def test_too_many_positional_options_are_rejected(self) -> None:
        args = (None,) * (len(_WEBRTC_STREAMER_OPTION_NAMES) + 1)

        with pytest.raises(TypeError, match="takes at most"):
            _normalize_webrtc_streamer_options(args, {})


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
