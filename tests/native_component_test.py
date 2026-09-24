import json
import subprocess
import sys
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

import streamlit_webrtc.component as component
from streamlit_webrtc.component import (
    WebRtcStreamerContext,
    WebRtcStreamerState,
    _handle_worker_lifecycle,
)
from streamlit_webrtc.webrtc import WebRtcMode


@pytest.fixture
def native_component(monkeypatch):
    native_module = ModuleType("streamlit_webrtc_native")
    native_module.AudioPeer = Mock()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "streamlit_webrtc_native", native_module)
    context: WebRtcStreamerContext[Any, Any] = WebRtcStreamerContext(
        worker=None, state=WebRtcStreamerState(playing=False, signalling=False)
    )
    render = Mock(return_value=None)
    lifecycle = Mock()
    monkeypatch.setattr(component, "_component_func", render)
    monkeypatch.setattr(component, "_get_or_create_context", lambda key: context)
    monkeypatch.setattr(component, "_handle_worker_lifecycle", lifecycle)
    monkeypatch.setattr(
        component, "_restore_snapshot_if_needed", lambda context, value: value
    )
    return SimpleNamespace(context=context, render=render, lifecycle=lifecycle)


def test_native_default_negotiates_only_audio(native_component):
    context = component.webrtc_streamer(key="native", backend="native")

    assert context is native_component.context
    args = native_component.render.call_args.kwargs
    assert args["media_stream_constraints"] == {"audio": True, "video": False}
    assert args["sendback_video"] is False
    assert args["sendback_audio"] is True
    assert args["mode"] == "SENDRECV"


def test_native_accepts_audio_constraint_dictionary(native_component):
    constraints = {"audio": {}, "video": False}
    component.webrtc_streamer(
        key="native", backend="native", media_stream_constraints=constraints
    )

    assert (
        native_component.render.call_args.kwargs["media_stream_constraints"]
        == constraints
    )


@pytest.mark.parametrize("backend", ["aiortc", "native"])
def test_backend_selects_worker_with_server_configuration(
    native_component, monkeypatch, backend
):
    native_worker = Mock()
    aiortc_worker = Mock()
    monkeypatch.setattr(component, "NativeAudioWorker", native_worker)
    monkeypatch.setattr(component, "WebRtcWorker", aiortc_worker)
    callback = Mock()
    on_ended = Mock()

    component.webrtc_streamer(
        key="native",
        backend=backend,
        server_rtc_configuration={"iceServers": []},
        audio_frame_callback=callback,
        on_audio_ended=on_ended,
        async_processing=False,
    )
    native_component.lifecycle.call_args.kwargs["make_worker"]()

    selected, unused = (
        (native_worker, aiortc_worker)
        if backend == "native"
        else (aiortc_worker, native_worker)
    )
    selected.assert_called_once()
    unused.assert_not_called()
    args = selected.call_args.kwargs
    assert args["rtc_configuration"].iceServers == []
    assert args["audio_frame_callback"] is callback
    assert args["on_audio_ended"] is on_ended
    assert args["async_processing"] is False


def test_native_answer_is_forwarded_without_aiortc_peer_connection(
    native_component, monkeypatch
):
    answer = SimpleNamespace(sdp="native answer", type="answer")
    worker = Mock(
        spec=["backend", "local_description", "process_offer", "update_audio_callbacks"]
    )
    worker.backend = "native"
    worker.local_description = answer
    monkeypatch.setattr(component, "NativeAudioWorker", Mock(return_value=worker))
    monkeypatch.setattr(component, "_handle_worker_lifecycle", _handle_worker_lifecycle)
    rerun = Mock()
    monkeypatch.setattr(component, "rerun", rerun)
    native_component.context._set_state(
        WebRtcStreamerState(playing=False, signalling=True)
    )
    native_component.render.return_value = {
        "sdpOffer": {"sdp": "browser offer", "type": "offer"}
    }

    component.webrtc_streamer(
        key="native", backend="native", server_rtc_configuration={"iceServers": []}
    )

    worker.process_offer.assert_called_once_with("browser offer", "offer", timeout=10.0)
    assert json.loads(native_component.context._sdp_answer_json) == {
        "sdp": "native answer",
        "type": "answer",
    }
    assert native_component.context._get_worker() is worker
    rerun.assert_called_once()


@pytest.mark.parametrize("mode", [WebRtcMode.SENDONLY, WebRtcMode.RECVONLY])
def test_native_rejects_unsupported_mode_before_render(native_component, mode):
    with pytest.raises(ValueError, match="SENDRECV"):
        component.webrtc_streamer(key="native", backend="native", mode=mode)

    native_component.render.assert_not_called()
    native_component.lifecycle.assert_not_called()


@pytest.mark.parametrize(
    "constraints",
    [
        {"audio": True, "video": True},
        {"audio": True, "video": {}},
        {"audio": False, "video": False},
        {"video": False},
        {},
    ],
)
def test_native_rejects_non_audio_capture_before_render(native_component, constraints):
    with pytest.raises(ValueError, match="audio|video"):
        component.webrtc_streamer(
            key="native", backend="native", media_stream_constraints=constraints
        )

    native_component.render.assert_not_called()
    native_component.lifecycle.assert_not_called()


@pytest.mark.parametrize(
    "option",
    [
        "player_factory",
        "in_recorder_factory",
        "out_recorder_factory",
        "video_frame_callback",
        "queued_video_frames_callback",
        "queued_audio_frames_callback",
        "on_video_ended",
        "video_processor_factory",
        "audio_processor_factory",
        "source_video_track",
        "source_audio_track",
        "sink_video_track",
        "sink_audio_track",
    ],
)
def test_native_rejects_unsupported_option_before_render(native_component, option):
    options: dict[str, Any] = {option: Mock()}
    with pytest.raises(ValueError, match=option):
        component.webrtc_streamer(key="native", backend="native", **options)

    native_component.render.assert_not_called()
    native_component.lifecycle.assert_not_called()


def test_native_rejects_disabling_return_audio(native_component):
    with pytest.raises(ValueError, match="sendback_audio"):
        component.webrtc_streamer(key="native", backend="native", sendback_audio=False)

    native_component.render.assert_not_called()


def test_unknown_backend_rejected_before_render(native_component):
    options: dict[str, Any] = {"backend": "unknown"}
    with pytest.raises(ValueError, match="backend"):
        component.webrtc_streamer(key="native", **options)

    native_component.render.assert_not_called()


def test_missing_native_dependency_explains_installation(native_component, monkeypatch):
    monkeypatch.setitem(sys.modules, "streamlit_webrtc_native", None)

    with pytest.raises(ImportError, match="[Ii]nstall|wheel"):
        component.webrtc_streamer(key="native", backend="native")

    native_component.render.assert_not_called()


@pytest.mark.parametrize(
    ("active_backend", "requested_backend"),
    [("aiortc", "native"), ("native", "aiortc")],
)
@pytest.mark.parametrize("signalling", [False, True])
def test_active_worker_backend_cannot_change(
    native_component, active_backend, requested_backend, signalling
):
    worker = Mock(backend=active_backend)
    native_component.context._set_worker(worker)
    native_component.context._set_state(
        WebRtcStreamerState(playing=not signalling, signalling=signalling)
    )

    with pytest.raises(ValueError, match="backend|[Ss]top"):
        component.webrtc_streamer(key="native", backend=requested_backend)

    native_component.render.assert_not_called()
    worker.stop.assert_not_called()


@pytest.mark.parametrize(
    ("active_backend", "requested_backend"),
    [("aiortc", "native"), ("native", "aiortc")],
)
def test_stopped_worker_allows_backend_change(
    native_component, monkeypatch, active_backend, requested_backend
):
    worker = Mock(backend=active_backend)
    context = native_component.context
    context._set_worker(worker)
    context._sdp_answer_json = '{"sdp": "stale answer", "type": "answer"}'
    context._is_sdp_answer_sent = True
    monkeypatch.setattr(component, "_handle_worker_lifecycle", _handle_worker_lifecycle)
    rerun = Mock()
    monkeypatch.setattr(component, "rerun", rerun)

    component.webrtc_streamer(key="native", backend=requested_backend)

    worker.stop.assert_called_once()
    assert context._get_worker() is None
    assert context._sdp_answer_json is None
    assert context._is_sdp_answer_sent is False
    assert native_component.render.call_args.kwargs["sdp_answer_json"] is None
    rerun.assert_not_called()


def test_native_rerun_can_remove_audio_callback(native_component):
    worker = Mock(backend="native")
    native_component.context._set_worker(worker)
    native_component.context._set_state(
        WebRtcStreamerState(playing=True, signalling=False)
    )
    callback = Mock(side_effect=lambda frame: frame)
    on_ended = Mock()

    component.webrtc_streamer(
        key="native",
        backend="native",
        audio_frame_callback=callback,
        on_audio_ended=on_ended,
    )
    worker.update_audio_callbacks.assert_called_once_with(
        frame_callback=callback, queued_frames_callback=None, on_ended=on_ended
    )
    worker.update_audio_callbacks.reset_mock()

    component.webrtc_streamer(key="native", backend="native")

    worker.update_audio_callbacks.assert_called_once_with(
        frame_callback=None, queued_frames_callback=None, on_ended=None
    )


def test_aiortc_default_does_not_import_native_binary():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import sys
from unittest.mock import Mock

class BlockNativeImport:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "streamlit_webrtc_native" or fullname.startswith("streamlit_webrtc_native."):
            raise AssertionError("The default backend imported the optional native binary")

sys.meta_path.insert(0, BlockNativeImport())
import streamlit_webrtc.component as component

component._component_func = Mock(return_value=None)
component._handle_worker_lifecycle = Mock()
component.webrtc_streamer(key="default")
""",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
