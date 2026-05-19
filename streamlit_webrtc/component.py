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
    List,
    NamedTuple,
    Optional,
    TypeVar,
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
from streamlit_webrtc.sink import MediaSink

from ._compat import cache_data, rerun
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


_T = TypeVar("_T")


class _WorkerForwarded(Generic[_T]):
    """Read-only descriptor that forwards attribute access to the live worker.

    Returns ``None`` when no worker is attached — the worker is held via a
    weakref on the enclosing context, so it can also disappear under us
    between accesses. The overloaded ``__get__`` lets type checkers see the
    attribute as ``Optional[_T]`` on instance access.
    """

    def __init__(self, attr_name: str) -> None:
        self._attr_name = attr_name

    @overload
    def __get__(
        self, instance: None, owner: Optional[type] = None
    ) -> "_WorkerForwarded[_T]": ...
    @overload
    def __get__(self, instance: Any, owner: Optional[type] = None) -> Optional[_T]: ...
    def __get__(self, instance: Any, owner: Optional[type] = None) -> Any:
        if instance is None:
            return self
        worker = instance._get_worker()
        return getattr(worker, self._attr_name) if worker else None


class WebRtcStreamerContext(Generic[VideoProcessorT, AudioProcessorT]):
    _state: WebRtcStreamerState
    _worker_ref: "Optional[weakref.ReferenceType[WebRtcWorker[VideoProcessorT, AudioProcessorT]]]"  # noqa

    _component_value_snapshot: Union[ComponentValueSnapshot, None]
    _worker_creation_lock: threading.Lock
    _sdp_answer_json: Optional[str]
    _is_sdp_answer_sent: bool

    # Passthrough attributes forwarded to the worker. Each returns the
    # worker's attribute when a worker is attached, otherwise None.
    video_receiver = _WorkerForwarded[VideoReceiver]("video_receiver")
    audio_receiver = _WorkerForwarded[AudioReceiver]("audio_receiver")
    source_video_track = _WorkerForwarded[MediaStreamTrack]("source_video_track")
    source_audio_track = _WorkerForwarded[MediaStreamTrack]("source_audio_track")
    sink_video_track = _WorkerForwarded[MediaSink]("sink_video_track")
    sink_audio_track = _WorkerForwarded[MediaSink]("sink_audio_track")
    input_video_track = _WorkerForwarded[MediaStreamTrack]("input_video_track")
    input_audio_track = _WorkerForwarded[MediaStreamTrack]("input_audio_track")
    output_video_track = _WorkerForwarded[MediaStreamTrack]("output_video_track")
    output_audio_track = _WorkerForwarded[MediaStreamTrack]("output_audio_track")

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


def _validate_sink_conflicts(
    *,
    kind: str,
    sink: Optional[MediaSink],
    frame_callback: Optional[Callable],
    queued_frames_callback: Optional[Callable],
    on_ended: Optional[Callable],
    processor_factory: Optional[Callable],
) -> None:
    """Reject combinations where the same kind has both a sink and a per-frame
    consumer wired through ``webrtc_streamer()``.

    Sinks are an alternative input strategy: routing the same upstream to a
    sink *and* a per-frame callback / processor would silently fan-out the
    stream, which is rarely what the caller intended and is easy to express
    explicitly via two consumers attached to one upstream relay when it is.
    """
    if sink is None:
        return
    conflicting: List[str] = []
    if frame_callback is not None:
        conflicting.append(f"{kind}_frame_callback")
    if queued_frames_callback is not None:
        conflicting.append(f"queued_{kind}_frames_callback")
    if on_ended is not None:
        conflicting.append(f"on_{kind}_ended")
    if processor_factory is not None:
        conflicting.append(f"{kind}_processor_factory")
    if conflicting:
        raise ValueError(
            f"sink_{kind}_track is mutually exclusive with "
            f"{', '.join(conflicting)} — choose one input strategy per kind."
        )


def generate_frontend_component_key(original_key: str) -> str:
    # The frontend component is registered in `st.session_state` under a key
    # that must not collide with the user's own `key=` (which we also store
    # the `WebRtcStreamerContext` under). Appending a long, unlikely-to-be-typed
    # suffix is the simplest collision avoidance — it's our salt, not a secret.
    return original_key + r':frontend 6)r])0Gea7e#2E#{y^i*_UzwU"@RJP<z'


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


def _get_or_create_context(key: str) -> WebRtcStreamerContext:
    """Return the per-key `WebRtcStreamerContext` from `st.session_state`,
    creating one if absent."""
    if key in st.session_state:
        context = st.session_state[key]

        # Substitute for `isinstance(context, WebRtcStreamerContext)`. Under
        # Streamlit's script-rerun mechanism, the class object's identity
        # changes between runs, so `isinstance` returns False even when the
        # object is in fact a `WebRtcStreamerContext`. Compare by class
        # *name* instead.
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
        # The SDP answer was set in a previous run and forwarded to the
        # frontend in this run via the component args; mark it sent so the
        # next `_handle_worker_lifecycle` call doesn't trigger another rerun.
        context._is_sdp_answer_sent = True

    return context


def _make_state_change_callback(
    key: str,
    frontend_key: str,
    user_on_change: Optional[Callable],
) -> Callable[[], None]:
    """Build the `on_change` callback handed to `_component_func`.

    Reads the latest component value out of `st.session_state`, computes the
    new `WebRtcStreamerState`, writes it back onto the context, and forwards
    to the user-supplied `on_change` only when the state actually changed.
    """

    def callback() -> None:
        component_value = st.session_state[frontend_key]
        new_state = compile_state(component_value)

        context = st.session_state[key]
        old_state = context.state
        context._set_state(new_state)

        if user_on_change and old_state != new_state:
            user_on_change()

    return callback


def _restore_snapshot_if_needed(
    context: WebRtcStreamerContext,
    component_value: Union[Dict, None],
) -> Union[Dict, None]:
    """Workaround for component-value loss across `rerun()`.

    When multiple `webrtc_streamer()` components live in the same script and
    one of them triggers `rerun()`, the *other* instances see their
    component value reset to `None` in the next run. Restore the most
    recent snapshot when that pattern is detected, and stash the current
    value for the next run regardless.
    """
    session_info = get_this_session_info()
    run_count = get_script_run_count(session_info) if session_info else None
    if component_value is None:
        restored = context._component_value_snapshot
        if (
            restored is not None
            # Only the snapshot from the immediately-prior run is
            # restored, so this workaround only fires for the rerun case.
            and run_count == restored.run_count + 1
        ):
            LOGGER.debug("Restore the component value")
            component_value = restored.component_value
    if run_count is not None:
        context._component_value_snapshot = ComponentValueSnapshot(
            component_value=component_value, run_count=run_count
        )
    return component_value


def _resolve_server_rtc_configuration(
    server_rtc_configuration: Optional[Union[Dict[str, Any], RTCConfiguration]],
) -> AiortcRTCConfiguration:
    """Convert the user-supplied server RTC configuration into the aiortc
    equivalent, filling in default ICE servers when none were given."""
    config = (
        compile_rtc_configuration(server_rtc_configuration)
        if server_rtc_configuration and isinstance(server_rtc_configuration, dict)
        else AiortcRTCConfiguration()
    )
    if config.iceServers is None:
        LOGGER.info(
            "rtc_configuration.iceServers is not set. Try to set it automatically."
        )
        # NOTE: `get_available_ice_servers()` may include a yield point where
        # Streamlit's script runner interrupts execution and stops the run.
        config.iceServers = compile_ice_servers(get_available_ice_servers())
    return config


def _handle_worker_lifecycle(
    context: WebRtcStreamerContext,
    key: str,
    sdp_offer: Optional[Dict],
    *,
    make_worker: Callable[[], "WebRtcWorker"],
) -> None:
    """Reconcile the worker against the frontend's current state.

    Three sub-cases, in order:

    - **Stop**: the frontend is idle but a worker is alive. Tear it down
      and `rerun()` so the SDP answer args get cleared from the frontend.
    - **Create**: there is no worker but the frontend offered an SDP.
      Construct a worker under the creation lock and feed it the offer.
    - **Flush answer**: a worker has produced a local description that the
      frontend hasn't seen yet. Stash it on the context and `rerun()` so
      the next run forwards it as a component arg.
    """
    # --- Stop ---
    if not context.state.playing and not context.state.signalling:
        LOGGER.debug(
            "The frontend state is neither playing nor signalling (key=%s).", key
        )

        worker_to_stop = context._get_worker()
        if worker_to_stop:
            LOGGER.debug("Stop the worker (key=%s).", key)
            worker_to_stop.stop()
            context._set_worker(None)
            context._is_sdp_answer_sent = False
            context._sdp_answer_json = None
            # Rerun to unset the SDP answer from the frontend args
            rerun()

    # --- Create ---
    # This point can be reached in parallel, so the lock makes worker
    # creation atomic.
    with context._worker_creation_lock:
        if not context._get_worker() and sdp_offer:
            LOGGER.debug(
                "No worker exists though the offer SDP is set. "
                'Create a new worker (key="%s").',
                key,
            )
            worker = make_worker()
            worker.process_offer(
                sdp_offer["sdp"],
                sdp_offer["type"],
                # aioice's internal method uses a 5s timeout
                # (https://github.com/aiortc/aioice/blob/aaada959aa8de31b880822db36f1c0c0cef75c0e/src/aioice/ice.py#L973);
                # give a bit more headroom here.
                timeout=10,
            )
            context._set_worker(worker)

    # --- Flush answer ---
    running_worker = context._get_worker()
    if (
        running_worker
        and running_worker.pc.localDescription
        and not context._is_sdp_answer_sent
    ):
        context._sdp_answer_json = json.dumps(
            {
                "sdp": running_worker.pc.localDescription.sdp,
                "type": running_worker.pc.localDescription.type,
            }
        )
        LOGGER.debug("Rerun to send the SDP answer to frontend")
        # NOTE: rerun() may not work if it's called inside the lock when the
        # `runner.fastReruns` config is enabled, because
        # `ScriptRequests._state` may have already been set to
        # `ScriptRequestType.STOP` by the rerun request issued from the
        # frontend while we were awaiting the lock — which would make a
        # rerun request from inside the lock get refused. Call it here
        # (outside the lock) instead. Crossing threads is fine as long as
        # the condition holds.
        rerun()


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
    sink_video_track: Optional[MediaSink] = None,
    sink_audio_track: Optional[MediaSink] = None,
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
    sink_video_track: Optional[MediaSink] = None,
    sink_audio_track: Optional[MediaSink] = None,
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
    sink_video_track: Optional[MediaSink] = None,
    sink_audio_track: Optional[MediaSink] = None,
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
    sink_video_track: Optional[MediaSink] = None,
    sink_audio_track: Optional[MediaSink] = None,
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
    sink_video_track: Optional[MediaSink] = None,
    sink_audio_track: Optional[MediaSink] = None,
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

    _validate_sink_conflicts(
        kind="video",
        sink=sink_video_track,
        frame_callback=video_frame_callback,
        queued_frames_callback=queued_video_frames_callback,
        on_ended=on_video_ended,
        processor_factory=video_processor_factory,
    )
    _validate_sink_conflicts(
        kind="audio",
        sink=sink_audio_track,
        frame_callback=audio_frame_callback,
        queued_frames_callback=queued_audio_frames_callback,
        on_ended=on_audio_ended,
        processor_factory=audio_processor_factory,
    )

    context = _get_or_create_context(key)
    frontend_key = generate_frontend_component_key(key)

    component_value: Union[Dict, None] = _component_func(
        key=frontend_key,
        # The user-supplied `key` scopes per-instance persistence (e.g.
        # device selection) in the frontend's localStorage. `frontend_key`
        # carries an obfuscation suffix that's irrelevant here, so we
        # forward the original `key` instead.
        component_key=key,
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
        # `sendback_*` lets the frontend negotiate recvonly transceivers for
        # kinds the local capture won't produce — without this, an audio-only
        # capture cannot receive a server-generated video stream.
        sendback_video=sendback_video,
        sendback_audio=sendback_audio,
        on_change=_make_state_change_callback(key, frontend_key, on_change),
    )
    component_value = _restore_snapshot_if_needed(context, component_value)

    sdp_offer = component_value.get("sdpOffer") if component_value else None

    _handle_worker_lifecycle(
        context,
        key,
        sdp_offer,
        make_worker=lambda: WebRtcWorker(
            mode=mode,
            rtc_configuration=_resolve_server_rtc_configuration(
                server_rtc_configuration
            ),
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
            sink_video_track=sink_video_track,
            sink_audio_track=sink_audio_track,
            sendback_video=sendback_video,
            sendback_audio=sendback_audio,
        ),
    )

    worker = context._get_worker()
    if worker is not None:
        if component_value and component_value.get("iceCandidates"):
            worker.set_ice_candidates_from_offerer(component_value["iceCandidates"])

        if video_frame_callback or queued_video_frames_callback or on_video_ended:
            worker.update_video_callbacks(
                frame_callback=video_frame_callback,
                queued_frames_callback=queued_video_frames_callback,
                on_ended=on_video_ended,
            )
        if audio_frame_callback or queued_audio_frames_callback or on_audio_ended:
            worker.update_audio_callbacks(
                frame_callback=audio_frame_callback,
                queued_frames_callback=queued_audio_frames_callback,
                on_ended=on_audio_ended,
            )

    return context
