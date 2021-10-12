import json
import logging
import os
import weakref
from typing import Any, Dict, Generic, NamedTuple, Optional, Union, overload

from aiortc.mediastreams import MediaStreamTrack

try:
    from typing import TypedDict
except ImportError:
    # Python < 3.8
    from typing_extensions import TypedDict

import streamlit as st
import streamlit.components.v1 as components

from .config import (
    DEFAULT_AUDIO_HTML_ATTRS,
    DEFAULT_MEDIA_STREAM_CONSTRAINTS,
    DEFAULT_VIDEO_HTML_ATTRS,
    AudioHTMLAttributes,
    MediaStreamConstraints,
    RTCConfiguration,
    VideoHTMLAttributes,
)
from .session_info import get_this_session_info
from .webrtc import (
    AudioProcessorFactory,
    AudioProcessorT,
    AudioReceiver,
    MediaPlayerFactory,
    MediaRecorderFactory,
    VideoProcessorFactory,
    VideoProcessorT,
    VideoReceiver,
    WebRtcMode,
    WebRtcWorker,
)

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


class ClientSettings(TypedDict, total=False):
    rtc_configuration: RTCConfiguration
    media_stream_constraints: MediaStreamConstraints


class WebRtcStreamerState(NamedTuple):
    playing: bool
    signalling: bool


# To restore component value after `streamlit.experimental_rerun()`.
class ComponentValueSnapshot(NamedTuple):
    component_value: Union[Dict, None]
    run_count: int


class WebRtcStreamerContext(Generic[VideoProcessorT, AudioProcessorT]):
    _state: WebRtcStreamerState
    _worker_ref: "Optional[weakref.ReferenceType[WebRtcWorker[VideoProcessorT, AudioProcessorT]]]"  # noqa

    _component_value_snapshot: Union[ComponentValueSnapshot, None]

    def __init__(
        self,
        worker: Optional[WebRtcWorker[VideoProcessorT, AudioProcessorT]],
        state: WebRtcStreamerState,
    ) -> None:
        self._set_worker(worker)
        self._set_state(state)
        self._component_value_snapshot = None

    def _set_worker(
        self, worker: Optional[WebRtcWorker[VideoProcessorT, AudioProcessorT]]
    ):
        self._worker_ref = weakref.ref(worker) if worker else None

    def _get_worker(self) -> Optional[WebRtcWorker[VideoProcessorT, AudioProcessorT]]:
        return self._worker_ref() if self._worker_ref else None

    def _set_state(self, state: WebRtcStreamerState):
        self._state = state

    @property
    def state(self) -> WebRtcStreamerState:
        return self._state

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
    def source_video_track(self) -> Optional[MediaStreamTrack]:
        worker = self._get_worker()
        return worker.source_video_track if worker else None

    @property
    def source_audio_track(self) -> Optional[MediaStreamTrack]:
        worker = self._get_worker()
        return worker.source_audio_track if worker else None

    @property
    def input_video_track(self) -> Optional[MediaStreamTrack]:
        worker = self._get_worker()
        return worker.input_video_track if worker else None

    @property
    def input_audio_track(self) -> Optional[MediaStreamTrack]:
        worker = self._get_worker()
        return worker.input_audio_track if worker else None

    @property
    def output_video_track(self) -> Optional[MediaStreamTrack]:
        worker = self._get_worker()
        return worker.output_video_track if worker else None

    @property
    def output_audio_track(self) -> Optional[MediaStreamTrack]:
        worker = self._get_worker()
        return worker.output_audio_track if worker else None


def generate_frontend_component_key(original_key: str) -> str:
    return (
        original_key + r':frontend 6)r])0Gea7e#2E#{y^i*_UzwU"@RJP<z'
    )  # Random string to avoid conflicts.
    # XXX: Any other cleaner way to ensure the key does not conflict?


@overload
def webrtc_streamer(
    key: str,
    mode: WebRtcMode = WebRtcMode.SENDRECV,
    rtc_configuration: Optional[Union[Dict, RTCConfiguration]] = None,
    media_stream_constraints: Optional[Union[Dict, MediaStreamConstraints]] = None,
    desired_playing_state: Optional[bool] = None,
    player_factory: Optional[MediaPlayerFactory] = None,
    in_recorder_factory: Optional[MediaRecorderFactory] = None,
    out_recorder_factory: Optional[MediaRecorderFactory] = None,
    video_processor_factory: None = None,
    audio_processor_factory: None = None,
    async_processing: bool = True,
    video_receiver_size: int = 4,
    audio_receiver_size: int = 4,
    source_video_track: Optional[MediaStreamTrack] = None,
    source_audio_track: Optional[MediaStreamTrack] = None,
    sendback_video: bool = True,
    sendback_audio: bool = True,
    video_html_attrs: Optional[Union[VideoHTMLAttributes, Dict]] = None,
    audio_html_attrs: Optional[Union[AudioHTMLAttributes, Dict]] = None,
    # Deprecated. Just for backward compatibility
    client_settings: Optional[Union[ClientSettings, Dict]] = None,
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
    rtc_configuration: Optional[Union[Dict, RTCConfiguration]] = None,
    media_stream_constraints: Optional[Union[Dict, MediaStreamConstraints]] = None,
    desired_playing_state: Optional[bool] = None,
    player_factory: Optional[MediaPlayerFactory] = None,
    in_recorder_factory: Optional[MediaRecorderFactory] = None,
    out_recorder_factory: Optional[MediaRecorderFactory] = None,
    video_processor_factory: Optional[VideoProcessorFactory[VideoProcessorT]] = None,
    audio_processor_factory: None = None,
    async_processing: bool = True,
    video_receiver_size: int = 4,
    audio_receiver_size: int = 4,
    source_video_track: Optional[MediaStreamTrack] = None,
    source_audio_track: Optional[MediaStreamTrack] = None,
    sendback_video: bool = True,
    sendback_audio: bool = True,
    video_html_attrs: Optional[Union[VideoHTMLAttributes, Dict]] = None,
    audio_html_attrs: Optional[Union[AudioHTMLAttributes, Dict]] = None,
    # Deprecated. Just for backward compatibility
    client_settings: Optional[Union[ClientSettings, Dict]] = None,
    video_transformer_factory: None = None,
    async_transform: Optional[bool] = None,
) -> WebRtcStreamerContext[VideoProcessorT, Any]:
    pass


@overload
def webrtc_streamer(
    key: str,
    mode: WebRtcMode = WebRtcMode.SENDRECV,
    rtc_configuration: Optional[Union[Dict, RTCConfiguration]] = None,
    media_stream_constraints: Optional[Union[Dict, MediaStreamConstraints]] = None,
    desired_playing_state: Optional[bool] = None,
    player_factory: Optional[MediaPlayerFactory] = None,
    in_recorder_factory: Optional[MediaRecorderFactory] = None,
    out_recorder_factory: Optional[MediaRecorderFactory] = None,
    video_processor_factory: None = None,
    audio_processor_factory: Optional[AudioProcessorFactory[AudioProcessorT]] = None,
    async_processing: bool = True,
    video_receiver_size: int = 4,
    audio_receiver_size: int = 4,
    source_video_track: Optional[MediaStreamTrack] = None,
    source_audio_track: Optional[MediaStreamTrack] = None,
    sendback_video: bool = True,
    sendback_audio: bool = True,
    video_html_attrs: Optional[Union[VideoHTMLAttributes, Dict]] = None,
    audio_html_attrs: Optional[Union[AudioHTMLAttributes, Dict]] = None,
    # Deprecated. Just for backward compatibility
    client_settings: Optional[Union[ClientSettings, Dict]] = None,
    video_transformer_factory: None = None,
    async_transform: Optional[bool] = None,
) -> WebRtcStreamerContext[Any, AudioProcessorT]:
    pass


@overload
def webrtc_streamer(
    key: str,
    mode: WebRtcMode = WebRtcMode.SENDRECV,
    rtc_configuration: Optional[Union[Dict, RTCConfiguration]] = None,
    media_stream_constraints: Optional[Union[Dict, MediaStreamConstraints]] = None,
    desired_playing_state: Optional[bool] = None,
    player_factory: Optional[MediaPlayerFactory] = None,
    in_recorder_factory: Optional[MediaRecorderFactory] = None,
    out_recorder_factory: Optional[MediaRecorderFactory] = None,
    video_processor_factory: Optional[VideoProcessorFactory[VideoProcessorT]] = None,
    audio_processor_factory: Optional[AudioProcessorFactory[AudioProcessorT]] = None,
    async_processing: bool = True,
    video_receiver_size: int = 4,
    audio_receiver_size: int = 4,
    source_video_track: Optional[MediaStreamTrack] = None,
    source_audio_track: Optional[MediaStreamTrack] = None,
    sendback_video: bool = True,
    sendback_audio: bool = True,
    video_html_attrs: Optional[Union[VideoHTMLAttributes, Dict]] = None,
    audio_html_attrs: Optional[Union[AudioHTMLAttributes, Dict]] = None,
    # Deprecated. Just for backward compatibility
    client_settings: Optional[Union[ClientSettings, Dict]] = None,
    video_transformer_factory: None = None,
    async_transform: Optional[bool] = None,
) -> WebRtcStreamerContext[VideoProcessorT, AudioProcessorT]:
    pass


def webrtc_streamer(
    key: str,
    mode: WebRtcMode = WebRtcMode.SENDRECV,
    rtc_configuration: Optional[Union[Dict, RTCConfiguration]] = None,
    media_stream_constraints: Optional[Union[Dict, MediaStreamConstraints]] = None,
    desired_playing_state: Optional[bool] = None,
    player_factory: Optional[MediaPlayerFactory] = None,
    in_recorder_factory: Optional[MediaRecorderFactory] = None,
    out_recorder_factory: Optional[MediaRecorderFactory] = None,
    video_processor_factory=None,
    audio_processor_factory=None,
    async_processing: bool = True,
    video_receiver_size: int = 4,
    audio_receiver_size: int = 4,
    source_video_track: Optional[MediaStreamTrack] = None,
    source_audio_track: Optional[MediaStreamTrack] = None,
    sendback_video: bool = True,
    sendback_audio: bool = True,
    video_html_attrs: Optional[Union[VideoHTMLAttributes, Dict]] = None,
    audio_html_attrs: Optional[Union[AudioHTMLAttributes, Dict]] = None,
    # Deprecated. Just for backward compatibility
    client_settings: Optional[Union[ClientSettings, Dict]] = None,
    video_transformer_factory=None,
    async_transform: Optional[bool] = None,
) -> WebRtcStreamerContext[VideoProcessorT, AudioProcessorT]:
    # Backward compatibility
    if video_transformer_factory is not None:
        LOGGER.warning(
            "The argument video_transformer_factory is deprecated. "
            "Use video_processor_factory instead."
        )
        video_processor_factory = video_transformer_factory
    if async_transform is not None:
        LOGGER.warning(
            "The argument async_transform is deprecated. "
            "Use async_processing instead."
        )
        async_processing = async_transform
    if client_settings is not None:
        LOGGER.warning(
            "The argument client_settings is deprecated. "
            "Use rtc_configuration and media_stream_constraints instead."
        )
        rtc_configuration = (
            client_settings.get("rtc_configuration") if client_settings else None
        )
        media_stream_constraints = (
            client_settings.get("media_stream_constraints") if client_settings else None
        )

    if media_stream_constraints is None:
        media_stream_constraints = DEFAULT_MEDIA_STREAM_CONSTRAINTS
    if video_html_attrs is None:
        video_html_attrs = DEFAULT_VIDEO_HTML_ATTRS
    if audio_html_attrs is None:
        audio_html_attrs = DEFAULT_AUDIO_HTML_ATTRS

    if key in st.session_state:
        context = st.session_state[key]

        # This if-clause below is an alternative to something like
        # `if not isinstance(context, WebRtcStreamerContext)`.
        # Under the Streamlit execution mechanism,
        # the identity of the class object `WebRtcStreamerContext` changes at each run,
        # so `isinstance` cannot be used.
        # Then, type().__name__ is used for this purpose instead.
        if type(context).__name__ != WebRtcStreamerContext.__name__:
            raise TypeError(
                f'st.session_state["{key}"] has an invalid type: {type(context)}'
            )
    else:
        context = WebRtcStreamerContext(
            worker=None, state=WebRtcStreamerState(playing=False, signalling=False)
        )
        st.session_state[key] = context

    webrtc_worker = context._get_worker()

    sdp_answer_json = None
    if webrtc_worker:
        sdp_answer_json = json.dumps(
            {
                "sdp": webrtc_worker.pc.localDescription.sdp,
                "type": webrtc_worker.pc.localDescription.type,
            }
        )

    component_value_raw: Union[Dict, str, None] = _component_func(
        key=generate_frontend_component_key(key),
        sdp_answer_json=sdp_answer_json,
        mode=mode.name,
        settings=client_settings,
        rtc_configuration=rtc_configuration,
        media_stream_constraints=media_stream_constraints,
        video_html_attrs=video_html_attrs,
        audio_html_attrs=audio_html_attrs,
        desired_playing_state=desired_playing_state,
    )
    # HOTFIX: The return value from _component_func()
    #         is of type str with streamlit==0.84.0.
    # See https://github.com/whitphx/streamlit-webrtc/issues/287
    component_value: Union[Dict, None]
    if isinstance(component_value_raw, str):
        LOGGER.warning("The component value is of type str")
        component_value = json.loads(component_value_raw)
    else:
        component_value = component_value_raw

    # HACK: Save the component value in this run to the session state
    # to be restored in the next run because the component values of
    # component instances behind the one which calls `streamlit.experimental_rerun()`
    # will not be held but be reset to the initial value in the next run.
    # For example, when there are two `webrtc_streamer()` component instances
    # in a script and `streamlit.experimental_rerun()` in the first one is called,
    # the component value of the second instance will be None in the next run
    # after `streamlit.experimental_rerun()`.
    session_info = get_this_session_info()
    run_count = session_info.report_run_count if session_info else None
    if component_value is None:
        restored_component_value_snapshot = context._component_value_snapshot
        if (
            restored_component_value_snapshot
            # Only the component value saved in the previous run is restored
            # so that this workaround is only effective in the case of
            # `streamlit.experimental_rerun()`.
            and run_count == restored_component_value_snapshot.run_count + 1
        ):
            LOGGER.debug("Restore the component value (key=%s)", key)
            component_value = restored_component_value_snapshot.component_value
    context._component_value_snapshot = ComponentValueSnapshot(
        component_value=component_value, run_count=run_count
    )

    playing = False
    sdp_offer = None
    if component_value:
        playing = component_value.get("playing", False)
        sdp_offer = component_value.get("sdpOffer")

    signalling = bool(sdp_offer)

    if webrtc_worker and not playing and not signalling:
        LOGGER.debug(
            "Unset the worker because the frontend state is "
            'neither playing nor signalling (key="%s").',
            key,
        )
        webrtc_worker.stop()
        context._set_worker(None)
        webrtc_worker = None
        # Rerun to unset the SDP answer from the frontend args
        st.experimental_rerun()

    if not webrtc_worker and sdp_offer:
        LOGGER.debug(
            "No worker exists though the offer SDP is set. "
            'Create a new worker (key="%s").',
            key,
        )
        webrtc_worker = WebRtcWorker(
            mode=mode,
            player_factory=player_factory,
            in_recorder_factory=in_recorder_factory,
            out_recorder_factory=out_recorder_factory,
            video_processor_factory=video_processor_factory,
            audio_processor_factory=audio_processor_factory,
            async_processing=async_processing,
            video_receiver_size=video_receiver_size,
            audio_receiver_size=audio_receiver_size,
            source_video_track=source_video_track,
            source_audio_track=source_audio_track,
            sendback_video=sendback_video,
            sendback_audio=sendback_audio,
        )
        webrtc_worker.process_offer(sdp_offer["sdp"], sdp_offer["type"])
        context._set_worker(webrtc_worker)
        # Rerun to send the SDP answer to frontend
        st.experimental_rerun()

    context._set_worker(webrtc_worker)
    context._set_state(WebRtcStreamerState(playing=playing, signalling=signalling))
    return context
