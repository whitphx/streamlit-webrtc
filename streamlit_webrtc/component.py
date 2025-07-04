import copy
import json
import logging
import os
import threading
import warnings
import weakref
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    NamedTuple,
    Optional,
    Union,
    cast,
    overload,
)

import streamlit as st
import streamlit.components.v1 as components
from aiortc import RTCConfiguration as AiortcRTCConfiguration
from aiortc.mediastreams import MediaStreamTrack

from streamlit_webrtc.models import (
    AudioFrameCallback,
    MediaEndedCallback,
    QueuedAudioFramesCallback,
    QueuedVideoFramesCallback,
    VideoFrameCallback,
)

from ._compat import VER_GTE_1_36_0, cache_data, rerun
from .components_callbacks import register_callback
from .config import (
    DEFAULT_AUDIO_HTML_ATTRS,
    DEFAULT_MEDIA_STREAM_CONSTRAINTS,
    DEFAULT_VIDEO_HTML_ATTRS,
    AudioHTMLAttributes,
    MediaStreamConstraints,
    RTCConfiguration,
    Translations,
    VideoHTMLAttributes,
    compile_ice_servers,
    compile_rtc_configuration,
)
from .credentials import (
    get_available_ice_servers,
)
from .session_info import get_script_run_count, get_this_session_info
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
        url="http://localhost:5173",
    )
else:
    parent_dir = os.path.dirname(os.path.abspath(__file__))
    build_dir = os.path.join(parent_dir, "frontend/dist")
    _component_func = components.declare_component("webrtc_streamer", path=build_dir)


class WebRtcStreamerState(NamedTuple):
    playing: bool
    signalling: bool


# To restore component value after `rerun()`.
class ComponentValueSnapshot(NamedTuple):
    component_value: Union[Dict, None]
    run_count: int


class WebRtcStreamerContext(Generic[VideoProcessorT, AudioProcessorT]):
    _state: WebRtcStreamerState
    _worker_ref: "Optional[weakref.ReferenceType[WebRtcWorker[VideoProcessorT, AudioProcessorT]]]"  # noqa

    _component_value_snapshot: Union[ComponentValueSnapshot, None]
    _worker_creation_lock: threading.Lock
    _sdp_answer_json: Optional[str]
    _is_sdp_answer_sent: bool

    def __init__(
        self,
        worker: Optional[WebRtcWorker[VideoProcessorT, AudioProcessorT]],
        state: WebRtcStreamerState,
    ) -> None:
        self._set_worker(worker)
        self._set_state(state)
        self._component_value_snapshot = None
        self._worker_creation_lock = threading.Lock()
        self._sdp_answer_json = None
        self._is_sdp_answer_sent = False

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

        # worker.video_processor is Union[VideoProcessorT, MediaCallbackContainer],
        # but the callback processor is usually not used through this property
        # as class-less callback API is used in that case,
        # so we can ignore that type here by casting the type into VideoProcessorT only.
        return cast(VideoProcessorT, worker.video_processor) if worker else None

    @property
    def audio_processor(self) -> Optional[AudioProcessorT]:
        """
        A audio processor instance which has been created through
        the callable provided as `audio_processor_factory` argument
        to `webrtc_streamer()`.
        """
        worker = self._get_worker()

        # worker.audio_processor is Union[AudioProcessorT, MediaCallbackContainer],
        # but the callback processor is usually not used through this property
        # as class-less callback API is used in that case,
        # so we can ignore that type here by casting the type into AudioProcessorT only.
        return cast(AudioProcessorT, worker.audio_processor) if worker else None

    @property
    def video_transformer(self) -> Optional[VideoProcessorT]:
        """
        A video transformer instance which has been created through
        the callable provided as `video_transformer_factory` argument
        to `webrtc_streamer()`.

        .. deprecated:: 0.20.0
        """
        worker = self._get_worker()
        return cast(VideoProcessorT, worker.video_processor) if worker else None

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


def compile_state(component_value) -> WebRtcStreamerState:
    playing = component_value.get("playing", False)
    signalling = bool(component_value.get("sdpOffer"))
    return WebRtcStreamerState(playing=playing, signalling=signalling)


@cache_data
def enhance_frontend_rtc_configuration(
    user_frontend_rtc_configuration: Optional[
        Union[Dict[str, Any], RTCConfiguration]
    ] = None,
) -> Union[Dict[str, Any], RTCConfiguration]:
    config = (
        copy.deepcopy(user_frontend_rtc_configuration)
        if user_frontend_rtc_configuration
        else {}
    )
    if config.get("iceServers") is None:
        LOGGER.info(
            "frontend_rtc_configuration.iceServers is not set. Try to set it automatically."
        )
        config["iceServers"] = get_available_ice_servers()
    return config


@overload
def webrtc_streamer(
    key: str,
    mode: WebRtcMode = WebRtcMode.SENDRECV,
    rtc_configuration: Optional[Union[Dict[str, Any], RTCConfiguration]] = None,
    server_rtc_configuration: Optional[Union[Dict[str, Any], RTCConfiguration]] = None,
    frontend_rtc_configuration: Optional[
        Union[Dict[str, Any], RTCConfiguration]
    ] = None,
    media_stream_constraints: Optional[Union[Dict, MediaStreamConstraints]] = None,
    desired_playing_state: Optional[bool] = None,
    player_factory: Optional[MediaPlayerFactory] = None,
    in_recorder_factory: Optional[MediaRecorderFactory] = None,
    out_recorder_factory: Optional[MediaRecorderFactory] = None,
    video_frame_callback: Optional[VideoFrameCallback] = None,
    audio_frame_callback: Optional[AudioFrameCallback] = None,
    queued_video_frames_callback: Optional[QueuedVideoFramesCallback] = None,
    queued_audio_frames_callback: Optional[QueuedAudioFramesCallback] = None,
    on_video_ended: Optional[MediaEndedCallback] = None,
    on_audio_ended: Optional[MediaEndedCallback] = None,
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
    translations: Optional[Translations] = None,
    on_change: Optional[Callable] = None,
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
    rtc_configuration: Optional[Union[Dict[str, Any], RTCConfiguration]] = None,
    server_rtc_configuration: Optional[Union[Dict[str, Any], RTCConfiguration]] = None,
    frontend_rtc_configuration: Optional[
        Union[Dict[str, Any], RTCConfiguration]
    ] = None,
    media_stream_constraints: Optional[Union[Dict, MediaStreamConstraints]] = None,
    desired_playing_state: Optional[bool] = None,
    player_factory: Optional[MediaPlayerFactory] = None,
    in_recorder_factory: Optional[MediaRecorderFactory] = None,
    out_recorder_factory: Optional[MediaRecorderFactory] = None,
    video_frame_callback: Optional[VideoFrameCallback] = None,
    audio_frame_callback: Optional[AudioFrameCallback] = None,
    queued_video_frames_callback: Optional[QueuedVideoFramesCallback] = None,
    queued_audio_frames_callback: Optional[QueuedAudioFramesCallback] = None,
    on_video_ended: Optional[MediaEndedCallback] = None,
    on_audio_ended: Optional[MediaEndedCallback] = None,
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
    translations: Optional[Translations] = None,
    on_change: Optional[Callable] = None,
    # Deprecated. Just for backward compatibility
    video_transformer_factory: None = None,
    async_transform: Optional[bool] = None,
) -> WebRtcStreamerContext[VideoProcessorT, Any]:
    pass


@overload
def webrtc_streamer(
    key: str,
    mode: WebRtcMode = WebRtcMode.SENDRECV,
    rtc_configuration: Optional[Union[Dict[str, Any], RTCConfiguration]] = None,
    server_rtc_configuration: Optional[Union[Dict[str, Any], RTCConfiguration]] = None,
    frontend_rtc_configuration: Optional[
        Union[Dict[str, Any], RTCConfiguration]
    ] = None,
    media_stream_constraints: Optional[Union[Dict, MediaStreamConstraints]] = None,
    desired_playing_state: Optional[bool] = None,
    player_factory: Optional[MediaPlayerFactory] = None,
    in_recorder_factory: Optional[MediaRecorderFactory] = None,
    out_recorder_factory: Optional[MediaRecorderFactory] = None,
    video_frame_callback: Optional[VideoFrameCallback] = None,
    audio_frame_callback: Optional[AudioFrameCallback] = None,
    queued_video_frames_callback: Optional[QueuedVideoFramesCallback] = None,
    queued_audio_frames_callback: Optional[QueuedAudioFramesCallback] = None,
    on_video_ended: Optional[MediaEndedCallback] = None,
    on_audio_ended: Optional[MediaEndedCallback] = None,
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
    translations: Optional[Translations] = None,
    on_change: Optional[Callable] = None,
    # Deprecated. Just for backward compatibility
    video_transformer_factory: None = None,
    async_transform: Optional[bool] = None,
) -> WebRtcStreamerContext[Any, AudioProcessorT]:
    pass


@overload
def webrtc_streamer(
    key: str,
    mode: WebRtcMode = WebRtcMode.SENDRECV,
    rtc_configuration: Optional[Union[Dict[str, Any], RTCConfiguration]] = None,
    server_rtc_configuration: Optional[Union[Dict[str, Any], RTCConfiguration]] = None,
    frontend_rtc_configuration: Optional[
        Union[Dict[str, Any], RTCConfiguration]
    ] = None,
    media_stream_constraints: Optional[Union[Dict, MediaStreamConstraints]] = None,
    desired_playing_state: Optional[bool] = None,
    player_factory: Optional[MediaPlayerFactory] = None,
    in_recorder_factory: Optional[MediaRecorderFactory] = None,
    out_recorder_factory: Optional[MediaRecorderFactory] = None,
    video_frame_callback: Optional[VideoFrameCallback] = None,
    audio_frame_callback: Optional[AudioFrameCallback] = None,
    queued_video_frames_callback: Optional[QueuedVideoFramesCallback] = None,
    queued_audio_frames_callback: Optional[QueuedAudioFramesCallback] = None,
    on_video_ended: Optional[MediaEndedCallback] = None,
    on_audio_ended: Optional[MediaEndedCallback] = None,
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
    translations: Optional[Translations] = None,
    on_change: Optional[Callable] = None,
    # Deprecated. Just for backward compatibility
    video_transformer_factory: None = None,
    async_transform: Optional[bool] = None,
) -> WebRtcStreamerContext[VideoProcessorT, AudioProcessorT]:
    pass


def webrtc_streamer(
    key: str,
    mode: WebRtcMode = WebRtcMode.SENDRECV,
    rtc_configuration: Optional[Union[Dict[str, Any], RTCConfiguration]] = None,
    server_rtc_configuration: Optional[Union[Dict[str, Any], RTCConfiguration]] = None,
    frontend_rtc_configuration: Optional[
        Union[Dict[str, Any], RTCConfiguration]
    ] = None,
    media_stream_constraints: Optional[Union[Dict, MediaStreamConstraints]] = None,
    desired_playing_state: Optional[bool] = None,
    player_factory: Optional[MediaPlayerFactory] = None,
    in_recorder_factory: Optional[MediaRecorderFactory] = None,
    out_recorder_factory: Optional[MediaRecorderFactory] = None,
    video_frame_callback: Optional[VideoFrameCallback] = None,
    audio_frame_callback: Optional[AudioFrameCallback] = None,
    queued_video_frames_callback: Optional[QueuedVideoFramesCallback] = None,
    queued_audio_frames_callback: Optional[QueuedAudioFramesCallback] = None,
    on_video_ended: Optional[MediaEndedCallback] = None,
    on_audio_ended: Optional[MediaEndedCallback] = None,
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
    translations: Optional[Translations] = None,
    on_change: Optional[Callable] = None,
    # Deprecated. Just for backward compatibility
    video_transformer_factory=None,
    async_transform: Optional[bool] = None,
) -> WebRtcStreamerContext[VideoProcessorT, AudioProcessorT]:
    # Backward compatibility
    if video_transformer_factory is not None:
        warnings.warn(
            "The argument video_transformer_factory is deprecated. "
            "Use video_processor_factory instead.\n"
            "See https://github.com/whitphx/streamlit-webrtc#for-users-since-versions-020",
            DeprecationWarning,
            stacklevel=2,
        )
        video_processor_factory = video_transformer_factory
    if async_transform is not None:
        warnings.warn(
            "The argument async_transform is deprecated. "
            "Use async_processing instead.\n"
            "See https://github.com/whitphx/streamlit-webrtc#for-users-since-versions-020",
            DeprecationWarning,
            stacklevel=2,
        )
        async_processing = async_transform

    # `rtc_configuration` is a shorthand to configure both frontend and server.
    # `frontend_rtc_configuration` or `server_rtc_configuration` are prioritized.
    if frontend_rtc_configuration is None:
        frontend_rtc_configuration = rtc_configuration
    if server_rtc_configuration is None:
        server_rtc_configuration = rtc_configuration

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

    if context._sdp_answer_json:
        # Set the flag not to trigger rerun() any more as `context._sdp_answer_json` is already set and will have been sent to the frontend in this run.
        context._is_sdp_answer_sent = True

    frontend_key = generate_frontend_component_key(key)

    def callback():
        component_value = st.session_state[frontend_key]
        new_state = compile_state(component_value)

        context = st.session_state[key]
        old_state = context.state

        context._set_state(new_state)

        if on_change and old_state != new_state:
            on_change()

    if not VER_GTE_1_36_0:
        register_callback(element_key=frontend_key, callback=callback)
        kwargs = {}
    else:
        kwargs = {
            "on_change": callback,
        }
    component_value_raw: Union[Dict, str, None] = _component_func(
        key=frontend_key,
        sdp_answer_json=context._sdp_answer_json,
        mode=mode.name,
        rtc_configuration=enhance_frontend_rtc_configuration(
            frontend_rtc_configuration
        ),
        media_stream_constraints=media_stream_constraints,
        video_html_attrs=video_html_attrs,
        audio_html_attrs=audio_html_attrs,
        translations=translations,
        desired_playing_state=desired_playing_state,
        **kwargs,
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
    # component instances behind the one which calls `rerun()`
    # will not be held but be reset to the initial value in the next run.
    # For example, when there are two `webrtc_streamer()` component instances
    # in a script and `rerun()` in the first one is called,
    # the component value of the second instance will be None in the next run
    # after `rerun()`.
    session_info = get_this_session_info()
    run_count = get_script_run_count(session_info) if session_info else None
    if component_value is None:
        restored_component_value_snapshot = context._component_value_snapshot
        if (
            restored_component_value_snapshot
            # Only the component value saved in the previous run is restored
            # so that this workaround is only effective in the case of `rerun()`.
            and run_count == restored_component_value_snapshot.run_count + 1
        ):
            LOGGER.debug("Restore the component value (key=%s)", key)
            component_value = restored_component_value_snapshot.component_value
    if run_count is not None:
        context._component_value_snapshot = ComponentValueSnapshot(
            component_value=component_value, run_count=run_count
        )

    sdp_offer = None
    ice_candidates = None
    if component_value:
        sdp_offer = component_value.get("sdpOffer")
        ice_candidates = component_value.get("iceCandidates")

    if not context.state.playing and not context.state.signalling:
        LOGGER.debug(
            "The frontend state is neither playing nor signalling (key=%s).",
            key,
        )

        webrtc_worker_to_stop = context._get_worker()
        if webrtc_worker_to_stop:
            LOGGER.debug("Stop the worker (key=%s).", key)
            webrtc_worker_to_stop.stop()
            context._set_worker(None)
            context._is_sdp_answer_sent = False
            context._sdp_answer_json = None
            # Rerun to unset the SDP answer from the frontend args
            rerun()

    with context._worker_creation_lock:  # This point can be reached in parallel so we need to use a lock to make the worker creation process atomic.
        if not context._get_worker() and sdp_offer:
            LOGGER.debug(
                "No worker exists though the offer SDP is set. "
                'Create a new worker (key="%s").',
                key,
            )

            aiortc_rtc_configuration = (
                compile_rtc_configuration(server_rtc_configuration)
                if server_rtc_configuration
                and isinstance(server_rtc_configuration, dict)
                else AiortcRTCConfiguration()
            )
            if aiortc_rtc_configuration.iceServers is None:
                LOGGER.info(
                    "rtc_configuration.iceServers is not set. Try to set it automatically."
                )
                ice_servers = get_available_ice_servers()  # NOTE: This may include a yield point where Streamlit's script runner interrupts the execution and may stop the current run.
                aiortc_rtc_configuration.iceServers = compile_ice_servers(ice_servers)

            worker_created_in_this_run: WebRtcWorker = WebRtcWorker(
                mode=mode,
                rtc_configuration=aiortc_rtc_configuration,
                player_factory=player_factory,
                in_recorder_factory=in_recorder_factory,
                out_recorder_factory=out_recorder_factory,
                video_frame_callback=video_frame_callback,
                audio_frame_callback=audio_frame_callback,
                queued_video_frames_callback=queued_video_frames_callback,
                queued_audio_frames_callback=queued_audio_frames_callback,
                on_video_ended=on_video_ended,
                on_audio_ended=on_audio_ended,
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

            worker_created_in_this_run.process_offer(
                sdp_offer["sdp"],
                sdp_offer["type"],
                timeout=10,  # The timeout of aioice's method that is used in the internal of this method is 5: https://github.com/aiortc/aioice/blob/aaada959aa8de31b880822db36f1c0c0cef75c0e/src/aioice/ice.py#L973. We set a bit longer timeout here.
            )

            # Set the worker here within the lock.
            context._set_worker(worker_created_in_this_run)

    webrtc_worker = context._get_worker()
    if webrtc_worker:
        if webrtc_worker.pc.localDescription and not context._is_sdp_answer_sent:
            context._sdp_answer_json = json.dumps(
                {
                    "sdp": webrtc_worker.pc.localDescription.sdp,
                    "type": webrtc_worker.pc.localDescription.type,
                }
            )

            LOGGER.debug("Rerun to send the SDP answer to frontend")
            # NOTE: rerun() may not work if it's called in the lock when the `runner.fastReruns` config is enabled
            # because the `ScriptRequests._state` is set to `ScriptRequestType.STOP` by the rerun request from the frontend sent during awaiting the lock,
            # which makes the rerun request refused.
            # So we call rerun() here. It can be called even in a different thread(run) from the one where the worker is created as long as the condition is met.
            rerun()

        if ice_candidates:
            webrtc_worker.set_ice_candidates_from_offerer(ice_candidates)

        if video_frame_callback or queued_video_frames_callback or on_video_ended:
            webrtc_worker.update_video_callbacks(
                frame_callback=video_frame_callback,
                queued_frames_callback=queued_video_frames_callback,
                on_ended=on_video_ended,
            )
        if audio_frame_callback or queued_audio_frames_callback or on_audio_ended:
            webrtc_worker.update_audio_callbacks(
                frame_callback=audio_frame_callback,
                queued_frames_callback=queued_audio_frames_callback,
                on_ended=on_audio_ended,
            )

    return context
