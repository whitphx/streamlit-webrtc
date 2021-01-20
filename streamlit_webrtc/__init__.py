"""streamlit-webrtc
"""

import json
import logging
import os
from typing import Callable, Dict, Hashable, NamedTuple, Optional, Union

try:
    from typing import TypedDict
except ImportError:
    # Python < 3.8
    from typing_extensions import TypedDict

try:
    import importlib.metadata as importlib_metadata
except ModuleNotFoundError:
    # Python < 3.8
    import importlib_metadata  # type: ignore

import streamlit as st
import streamlit.components.v1 as components

from . import SessionState
from .config import MediaStreamConstraints, RTCConfiguration
from .webrtc import (
    MediaPlayerFactory,
    MediaRecorderFactory,
    VideoReceiver,
    VideoTransformerBase,
    WebRtcMode,
    WebRtcWorker,
)

# Set __version__ dynamically base on metadata.
# https://github.com/python-poetry/poetry/issues/1036#issuecomment-489880822
# https://github.com/python-poetry/poetry/issues/144#issuecomment-623927302
# https://github.com/python-poetry/poetry/pull/2366#issuecomment-652418094
try:
    __version__ = importlib_metadata.version(__name__)
except importlib_metadata.PackageNotFoundError:
    pass

LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())

_RELEASE = True  # TODO: How to dynamically manage this variable?

if not _RELEASE:
    _component_func = components.declare_component(
        "webrtc_streamer",
        url="http://localhost:3001",
    )
else:
    parent_dir = os.path.dirname(os.path.abspath(__file__))
    build_dir = os.path.join(parent_dir, "frontend/build")
    _component_func = components.declare_component("webrtc_streamer", path=build_dir)


_session_state = SessionState.get(webrtc_workers={})


def _get_webrtc_worker(key: Hashable) -> Union[WebRtcWorker, None]:
    return _session_state.webrtc_workers.get(key)


def _set_webrtc_worker(key: Hashable, webrtc_worker: WebRtcWorker) -> None:
    _session_state.webrtc_workers[key] = webrtc_worker


def _unset_webrtc_worker(key: Hashable) -> None:
    del _session_state.webrtc_workers[key]


class ClientSettings(TypedDict):
    rtc_configuration: Optional[RTCConfiguration]
    media_stream_constraints: Optional[MediaStreamConstraints]


class WebRtcWorkerState(NamedTuple):
    playing: bool


class WebRtcWorkerContext(NamedTuple):
    state: WebRtcWorkerState
    video_transformer: Optional[VideoTransformerBase]
    video_receiver: Optional[VideoReceiver]


def webrtc_streamer(
    key: str,
    mode: WebRtcMode = WebRtcMode.SENDRECV,
    client_settings: Optional[ClientSettings] = None,
    player_factory: Optional[MediaPlayerFactory] = None,
    in_recorder_factory: Optional[MediaRecorderFactory] = None,
    out_recorder_factory: Optional[MediaRecorderFactory] = None,
    video_transformer_factory: Optional[Callable[[], VideoTransformerBase]] = None,
    async_transform: bool = True,
) -> WebRtcWorkerContext:
    webrtc_worker = _get_webrtc_worker(key)

    sdp_answer_json = None
    if webrtc_worker:
        sdp_answer_json = json.dumps(
            {
                "sdp": webrtc_worker.pc.localDescription.sdp,
                "type": webrtc_worker.pc.localDescription.type,
            }
        )

    component_value: Union[Dict, None] = _component_func(
        key=key,
        sdp_answer_json=sdp_answer_json,
        mode=mode.name,
        settings=client_settings,
    )

    playing = False
    if component_value:
        playing = component_value.get("playing", False)
        sdp_offer = component_value.get("sdpOffer")

        if webrtc_worker:
            if not playing:
                webrtc_worker.stop()
                _unset_webrtc_worker(key)
        else:
            if sdp_offer:
                webrtc_worker = WebRtcWorker(
                    mode=mode,
                    player_factory=player_factory,
                    in_recorder_factory=in_recorder_factory,
                    out_recorder_factory=out_recorder_factory,
                    video_transformer_factory=video_transformer_factory,
                    async_transform=async_transform,
                )
                webrtc_worker.process_offer(sdp_offer["sdp"], sdp_offer["type"])
                _set_webrtc_worker(key, webrtc_worker)
                st.experimental_rerun()  # Rerun to send the SDP answer to frontend

    ctx = WebRtcWorkerContext(
        state=WebRtcWorkerState(playing=playing),
        video_transformer=webrtc_worker.video_transformer if webrtc_worker else None,
        video_receiver=webrtc_worker.video_receiver if webrtc_worker else None,
    )

    return ctx
