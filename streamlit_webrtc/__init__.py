"""streamlit-webrtc
"""

import json
import logging
import os
import weakref
from typing import Any, Dict, Generic, Hashable, NamedTuple, Optional, Union, overload

from aiortc.mediastreams import MediaStreamTrack

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
from .eventloop import get_server_event_loop
from .webrtc import (
    AudioProcessorBase,
    AudioProcessorFactory,
    AudioProcessorT,
    AudioReceiver,
    MediaPlayerFactory,
    MediaRecorderFactory,
    VideoProcessorBase,
    VideoProcessorFactory,
    VideoProcessorT,
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


def _get_session_state():
    return SessionState.get(webrtc_workers={})


def _get_webrtc_worker(key: Hashable) -> Union[WebRtcWorker, None]:
    session_state = _get_session_state()
    return session_state.webrtc_workers.get(key)


def _set_webrtc_worker(key: Hashable, webrtc_worker: WebRtcWorker) -> None:
    session_state = _get_session_state()
    session_state.webrtc_workers[key] = webrtc_worker


def _unset_webrtc_worker(key: Hashable) -> None:
    session_state = _get_session_state()
    del session_state.webrtc_workers[key]


class ClientSettings(TypedDict, total=False):
    rtc_configuration: RTCConfiguration
    media_stream_constraints: MediaStreamConstraints


class WebRtcStreamerState(NamedTuple):
    playing: bool
    signalling: bool


class WebRtcStreamerContext(Generic[VideoProcessorT, AudioProcessorT]):
    state: WebRtcStreamerState
    _worker_ref: "Optional[weakref.ReferenceType[WebRtcWorker[VideoProcessorT, AudioProcessorT]]]"  # noqa

    def __init__(
        self,
        worker: Optional[WebRtcWorker[VideoProcessorT, AudioProcessorT]],
        state: WebRtcStreamerState,
    ) -> None:
        self._worker_ref = weakref.ref(worker) if worker else None
        self.state = state

    def _get_worker(self) -> Optional[WebRtcWorker[VideoProcessorT, AudioProcessorT]]:
        return self._worker_ref() if self._worker_ref else None

    @property
    def video_processor(self) -> Optional[VideoProcessorT]:
        """
        A video processor instance which has been created through
        the callable provided as `video_processor_factory` argument
        to `webrtc_streamer()`.
        """
        worker = self._get_worker()
        return worker.video_processor if worker else None

    @property
    def audio_processor(self) -> Optional[AudioProcessorT]:
        """
        A audio processor instance which has been created through
        the callable provided as `audio_processor_factory` argument
        to `webrtc_streamer()`.
        """
        worker = self._get_worker()
        return worker.audio_processor if worker else None

    @property
    def video_transformer(self) -> Optional[VideoProcessorT]:
        """
        A video transformer instance which has been created through
        the callable provided as `video_transformer_factory` argument
        to `webrtc_streamer()`.

        .. deprecated:: 0.20.0
        """
        worker = self._get_worker()
        return worker.video_processor if worker else None

    @property
    def video_receiver(self) -> Optional[VideoReceiver]:
        worker = self._get_worker()
        return worker.video_receiver if worker else None

    @property
    def audio_receiver(self) -> Optional[AudioReceiver]:
        worker = self._get_worker()
        return worker.audio_receiver if worker else None

    @property
    def video_output_track(self) -> Optional[MediaStreamTrack]:
        worker = self._get_worker()
        return worker.video_output_track if worker else None

    @property
    def audio_output_track(self) -> Optional[MediaStreamTrack]:
        worker = self._get_worker()
        return worker.audio_output_track if worker else None


@overload
def webrtc_streamer(
    key: str,
    mode: WebRtcMode = WebRtcMode.SENDRECV,
    client_settings: Optional[ClientSettings] = None,
    desired_playing_state: Optional[bool] = None,
    player_factory: Optional[MediaPlayerFactory] = None,
    in_recorder_factory: Optional[MediaRecorderFactory] = None,
    out_recorder_factory: Optional[MediaRecorderFactory] = None,
    video_processor_factory: None = None,
    audio_processor_factory: None = None,
    async_processing: bool = True,
    video_receiver_size: int = 4,
    audio_receiver_size: int = 4,
    input: Optional[WebRtcStreamerContext] = None,
    # Deprecated. Just for backward compatibility
    video_transformer_factory: None = None,
    async_transform: Optional[bool] = None,
) -> WebRtcStreamerContext:
    # XXX: We wanted something like `WebRtcStreamerContext[None, None]`
    # as the return value, but could not find a good solution
    # and use `Any` instaed as `WebRtcStreamerContext[Any, Any]`.
    # `WebRtcStreamerContext` is a shorthand of `WebRtcStreamerContext[Any, Any]`.
    pass


@overload
def webrtc_streamer(
    key: str,
    mode: WebRtcMode = WebRtcMode.SENDRECV,
    client_settings: Optional[ClientSettings] = None,
    desired_playing_state: Optional[bool] = None,
    player_factory: Optional[MediaPlayerFactory] = None,
    in_recorder_factory: Optional[MediaRecorderFactory] = None,
    out_recorder_factory: Optional[MediaRecorderFactory] = None,
    video_processor_factory: Optional[VideoProcessorFactory[VideoProcessorT]] = None,
    audio_processor_factory: None = None,
    async_processing: bool = True,
    video_receiver_size: int = 4,
    audio_receiver_size: int = 4,
    input: Optional[WebRtcStreamerContext] = None,
    # Deprecated. Just for backward compatibility
    video_transformer_factory: None = None,
    async_transform: Optional[bool] = None,
) -> WebRtcStreamerContext[VideoProcessorT, Any]:
    pass


@overload
def webrtc_streamer(
    key: str,
    mode: WebRtcMode = WebRtcMode.SENDRECV,
    client_settings: Optional[ClientSettings] = None,
    desired_playing_state: Optional[bool] = None,
    player_factory: Optional[MediaPlayerFactory] = None,
    in_recorder_factory: Optional[MediaRecorderFactory] = None,
    out_recorder_factory: Optional[MediaRecorderFactory] = None,
    video_processor_factory: None = None,
    audio_processor_factory: Optional[AudioProcessorFactory[AudioProcessorT]] = None,
    async_processing: bool = True,
    video_receiver_size: int = 4,
    audio_receiver_size: int = 4,
    input: Optional[WebRtcStreamerContext] = None,
    # Deprecated. Just for backward compatibility
    video_transformer_factory: None = None,
    async_transform: Optional[bool] = None,
) -> WebRtcStreamerContext[Any, AudioProcessorT]:
    pass


@overload
def webrtc_streamer(
    key: str,
    mode: WebRtcMode = WebRtcMode.SENDRECV,
    client_settings: Optional[ClientSettings] = None,
    desired_playing_state: Optional[bool] = None,
    player_factory: Optional[MediaPlayerFactory] = None,
    in_recorder_factory: Optional[MediaRecorderFactory] = None,
    out_recorder_factory: Optional[MediaRecorderFactory] = None,
    video_processor_factory: Optional[VideoProcessorFactory[VideoProcessorT]] = None,
    audio_processor_factory: Optional[AudioProcessorFactory[AudioProcessorT]] = None,
    async_processing: bool = True,
    video_receiver_size: int = 4,
    audio_receiver_size: int = 4,
    input: Optional[WebRtcStreamerContext] = None,
    # Deprecated. Just for backward compatibility
    video_transformer_factory: None = None,
    async_transform: Optional[bool] = None,
) -> WebRtcStreamerContext[VideoProcessorT, AudioProcessorT]:
    pass


def webrtc_streamer(
    key: str,
    mode: WebRtcMode = WebRtcMode.SENDRECV,
    client_settings: Optional[ClientSettings] = None,
    desired_playing_state: Optional[bool] = None,
    player_factory: Optional[MediaPlayerFactory] = None,
    in_recorder_factory: Optional[MediaRecorderFactory] = None,
    out_recorder_factory: Optional[MediaRecorderFactory] = None,
    video_processor_factory=None,
    audio_processor_factory=None,
    async_processing: bool = True,
    video_receiver_size: int = 4,
    audio_receiver_size: int = 4,
    input: Optional[WebRtcStreamerContext] = None,
    # Deprecated. Just for backward compatibility
    video_transformer_factory=None,
    async_transform: Optional[bool] = None,
) -> WebRtcStreamerContext[VideoProcessorT, AudioProcessorT]:
    # Backward compatibility
    if video_transformer_factory is not None:
        video_processor_factory = video_transformer_factory
    if async_transform is not None:
        async_processing = async_transform

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
        desired_playing_state=desired_playing_state,
    )

    playing = False
    sdp_offer = None
    if component_value:
        playing = component_value.get("playing", False)
        sdp_offer = component_value.get("sdpOffer")

    signalling = sdp_offer is not None

    # NOTE: Sometimes component_value can be None even if the frontend component
    #       has already been rendered and started working.
    #       Such cases should be ignored, then here `component_value`
    #       is checked in the if-clause.
    if component_value and webrtc_worker and not playing and not signalling:
        LOGGER.debug(
            "Unset the worker because the frontend state is "
            'neither playing nor signalling (key="%s").',
            key,
        )
        webrtc_worker.stop()
        _unset_webrtc_worker(key)
        webrtc_worker = None
        # Rerun to unset the SDP answer from the frontend args
        st.experimental_rerun()

    if not webrtc_worker and sdp_offer:
        LOGGER.debug(
            "No worker exists though the offer SDP is set. "
            'Create a new worker (key="%s").',
            key,
        )
        loop = get_server_event_loop()
        webrtc_worker = WebRtcWorker(
            loop=loop,
            mode=mode,
            player_factory=player_factory,
            in_recorder_factory=in_recorder_factory,
            out_recorder_factory=out_recorder_factory,
            video_processor_factory=video_processor_factory,
            audio_processor_factory=audio_processor_factory,
            async_processing=async_processing,
            video_receiver_size=video_receiver_size,
            audio_receiver_size=audio_receiver_size,
            source_video_track=input.video_output_track if input else None,
            source_audio_track=input.audio_output_track if input else None,
        )
        webrtc_worker.process_offer(sdp_offer["sdp"], sdp_offer["type"])
        _set_webrtc_worker(key, webrtc_worker)
        # Rerun to send the SDP answer to frontend
        st.experimental_rerun()

    ctx = WebRtcStreamerContext(
        state=WebRtcStreamerState(playing=playing, signalling=signalling),
        worker=webrtc_worker,
    )

    return ctx


# For backward compatibility
VideoTransformerFactory = VideoProcessorFactory


__all__ = [
    "MediaPlayerFactory",
    "MediaRecorderFactory",
    "AudioProcessorBase",
    "AudioProcessorFactory",
    "VideoReceiver",
    "VideoTransformerBase",
    "VideoTransformerFactory",
    "VideoProcessorBase",
    "VideoProcessorFactory",
    "WebRtcMode",
    "ClientSettings",
    "webrtc_streamer",
]
