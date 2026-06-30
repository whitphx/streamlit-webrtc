from typing import Any, Callable, Literal, Optional, Type, Union, cast, overload

import streamlit as st

from ._compat import get_script_run_ctx
from .eventloop import get_global_event_loop, loop_context
from .mix import MediaStreamMixTrack, MixerCallback
from .models import (
    AudioProcessorFactory,
    AudioProcessorT,
    CallbackAttachableProcessor,
    FrameCallback,
    FrameT,
    MediaEndedCallback,
    ProcessorFactory,
    QueuedVideoFramesCallback,
    VideoProcessorFactory,
    VideoProcessorT,
)
from .pcm_source import PcmAudioSource
from .process import (
    AsyncAudioProcessTrack,
    AsyncMediaProcessTrack,
    AsyncVideoProcessTrack,
    AudioProcessTrack,
    MediaProcessTrack,
    VideoProcessTrack,
)
from .relay import get_global_relay
from .shutdown import SessionShutdownObserver
from .sink import (
    AudioSinkCallback,
    AudioSinkTrack,
    VideoSinkCallback,
    VideoSinkTrack,
)
from .source import (
    AudioSourceCallback,
    AudioSourceTrack,
    VideoSourceCallback,
    VideoSourceTrack,
)

_PROCESSOR_TRACK_CACHE_KEY_PREFIX = "__PROCESSOR_TRACK_CACHE__"
LifecycleScope = Literal["webrtc-session", "streamlit-session"]


def _get_current_session_state() -> Any:
    ctx = get_script_run_ctx()
    if ctx is not None:
        session_state = getattr(ctx, "session_state", None)
        if session_state is not None:
            return session_state
    return st.session_state


def _validate_lifecycle_scope(lifecycle_scope: str) -> LifecycleScope:
    if lifecycle_scope not in ("webrtc-session", "streamlit-session"):
        raise ValueError(
            "lifecycle_scope must be 'webrtc-session' or 'streamlit-session'; "
            f"got {lifecycle_scope!r}"
        )
    return cast(LifecycleScope, lifecycle_scope)


def _install_cached_with_shutdown_observer(
    *,
    session_state: Any,
    cache_key: str,
    observer_cache_key: str,
    cached: Any,
    shutdown_callback: Callable[[], None],
) -> None:
    # A prior observer for this exact cache slot is tied to a now-stale cached
    # object. Stop it before replacing the object so its polling thread is not
    # leaked for the rest of the Streamlit session.
    old_observer = session_state.get(observer_cache_key)
    if isinstance(old_observer, SessionShutdownObserver):
        old_observer.stop()

    session_state[cache_key] = cached
    session_state[observer_cache_key] = SessionShutdownObserver(shutdown_callback)


def _attach_factory_lifecycle(
    *,
    session_state: Any,
    cache_key: str,
    observer_cache_key: str,
    lifecycle_target: Any,
    lifecycle_scope: LifecycleScope,
    stop_cached: Callable[[], None],
) -> Callable[[], None]:
    def reset_on_webrtc_session_end() -> None:
        observer = session_state.pop(observer_cache_key, None)
        if isinstance(observer, SessionShutdownObserver):
            observer.stop()
        session_state.pop(cache_key, None)
        stop_cached()

    setattr(lifecycle_target, "_streamlit_webrtc_lifecycle_scope", lifecycle_scope)
    setattr(
        lifecycle_target,
        "_streamlit_webrtc_reset_on_session_end",
        reset_on_webrtc_session_end,
    )
    return reset_on_webrtc_session_end


def _get_track_class(
    kind: Literal["video", "audio"], async_processing: bool
) -> Union[Type[MediaProcessTrack], Type[AsyncMediaProcessTrack]]:
    if kind == "video":
        if async_processing:
            return AsyncVideoProcessTrack
        else:
            return VideoProcessTrack
    elif kind == "audio":
        if async_processing:
            return AsyncAudioProcessTrack
        else:
            return AudioProcessTrack
    else:
        raise ValueError(f"Unsupported track type: {kind}")


# Overloads for the cases where the processor_factory is specified
@overload
def create_process_track(
    input_track,
    *,
    processor_factory: AudioProcessorFactory[AudioProcessorT],
    async_processing: Literal[False],
    frame_callback: Optional[FrameCallback] = None,
    queued_frames_callback: Optional[QueuedVideoFramesCallback] = None,
    on_ended: Optional[MediaEndedCallback] = None,
) -> AudioProcessTrack[AudioProcessorT]: ...


@overload
def create_process_track(
    input_track,
    *,
    processor_factory: AudioProcessorFactory[AudioProcessorT],
    async_processing: Literal[True] = True,
    frame_callback: Optional[FrameCallback] = None,
    queued_frames_callback: Optional[QueuedVideoFramesCallback] = None,
    on_ended: Optional[MediaEndedCallback] = None,
) -> AsyncAudioProcessTrack[AudioProcessorT]: ...


@overload
def create_process_track(
    input_track,
    *,
    processor_factory: VideoProcessorFactory[VideoProcessorT],
    async_processing: Literal[False],
    frame_callback: Optional[FrameCallback] = None,
    queued_frames_callback: Optional[QueuedVideoFramesCallback] = None,
    on_ended: Optional[MediaEndedCallback] = None,
) -> VideoProcessTrack[VideoProcessorT]: ...


@overload
def create_process_track(
    input_track,
    *,
    processor_factory: VideoProcessorFactory[VideoProcessorT],
    async_processing: Literal[True] = True,
    frame_callback: Optional[FrameCallback] = None,
    queued_frames_callback: Optional[QueuedVideoFramesCallback] = None,
    on_ended: Optional[MediaEndedCallback] = None,
) -> AsyncVideoProcessTrack[VideoProcessorT]: ...


# Overloads for the cases where the processor_factory is NOT specified
@overload
def create_process_track(
    input_track,
    *,
    frame_callback: FrameCallback[FrameT],
    async_processing: Literal[False],
    processor_factory: Literal[None] = None,
    queued_frames_callback: Optional[QueuedVideoFramesCallback] = None,
    on_ended: Optional[MediaEndedCallback] = None,
) -> MediaProcessTrack[CallbackAttachableProcessor[FrameT], FrameT]: ...


@overload
def create_process_track(
    input_track,
    *,
    frame_callback: FrameCallback[FrameT],
    processor_factory: Literal[None] = None,
    async_processing: Literal[True] = True,
    queued_frames_callback: Optional[QueuedVideoFramesCallback] = None,
    on_ended: Optional[MediaEndedCallback] = None,
) -> AsyncMediaProcessTrack[CallbackAttachableProcessor[FrameT], FrameT]: ...


def create_process_track(
    input_track,
    frame_callback: Optional[FrameCallback] = None,
    queued_frames_callback: Optional[QueuedVideoFramesCallback] = None,
    on_ended: Optional[MediaEndedCallback] = None,
    processor_factory: Optional[ProcessorFactory] = None,  # Old API
    async_processing=True,
) -> Union[MediaProcessTrack, AsyncMediaProcessTrack]:
    cache_key = _PROCESSOR_TRACK_CACHE_KEY_PREFIX + str(input_track.id)

    if cache_key in st.session_state:
        processor_track = st.session_state[cache_key]
        if not processor_factory:
            processor: CallbackAttachableProcessor = processor_track.processor
            processor.update_callbacks(
                frame_callback=frame_callback,
                queued_frames_callback=queued_frames_callback,
                ended_callback=on_ended,
            )
    else:
        if processor_factory:
            processor = processor_factory()
        else:
            processor = CallbackAttachableProcessor(
                frame_callback=frame_callback,
                queued_frames_callback=queued_frames_callback,
                ended_callback=on_ended,
            )
        Track = _get_track_class(input_track.kind, async_processing)
        loop = get_global_event_loop()
        relay = get_global_relay()
        with loop_context(loop):
            processor_track = Track(relay.subscribe(input_track), processor)
            st.session_state[cache_key] = processor_track

    return processor_track


_MIXER_TRACK_CACHE_KEY_PREFIX = "__MIXER_TRACK_CACHE__"


def create_mix_track(
    kind: str,
    mixer_callback: MixerCallback[FrameT],
    key: str,
    mixer_output_interval: float = 1 / 30,
) -> MediaStreamMixTrack[FrameT]:
    cache_key = _MIXER_TRACK_CACHE_KEY_PREFIX + key
    if cache_key in st.session_state:
        mixer_track: MediaStreamMixTrack = st.session_state[cache_key]
        mixer_track._update_mixer_callback(mixer_callback)
    else:
        mixer_track = MediaStreamMixTrack(
            kind=kind,
            mixer_callback=mixer_callback,
            mixer_output_interval=mixer_output_interval,
        )
        st.session_state[cache_key] = mixer_track
    return mixer_track


_VIDEO_SOURCE_TRACK_CACHE_KEY_PREFIX = "__VIDEO_SOURCE_TRACK_CACHE__"
_VIDEO_SOURCE_TRACK_SHUTDOWN_OBSERVER_CACHE_KEY_PREFIX = (
    "__VIDEO_SOURCE_TRACK_SHUTDOWN_OBSERVER_CACHE__"
)


def create_video_source_track(
    callback: VideoSourceCallback,
    key: str,
    fps=30,
    on_ended: Optional[Callable[[], None]] = None,
    lifecycle_scope: LifecycleScope = "webrtc-session",
) -> VideoSourceTrack:
    lifecycle_scope = _validate_lifecycle_scope(lifecycle_scope)
    session_state = _get_current_session_state()
    cache_key = _VIDEO_SOURCE_TRACK_CACHE_KEY_PREFIX + key
    observer_cache_key = _VIDEO_SOURCE_TRACK_SHUTDOWN_OBSERVER_CACHE_KEY_PREFIX + key
    is_new_track = False
    if (
        cache_key in session_state
        and isinstance(session_state[cache_key], VideoSourceTrack)
        and session_state[cache_key].kind == "video"
        and session_state[cache_key].readyState == "live"
    ):
        video_source_track: VideoSourceTrack = session_state[cache_key]
        video_source_track._callback = callback
        video_source_track._fps = fps
    else:
        video_source_track = VideoSourceTrack(callback=callback, fps=fps)
        is_new_track = True
    video_source_track._on_ended_callback = on_ended
    reset_on_webrtc_session_end = _attach_factory_lifecycle(
        session_state=session_state,
        cache_key=cache_key,
        observer_cache_key=observer_cache_key,
        lifecycle_target=video_source_track,
        lifecycle_scope=lifecycle_scope,
        stop_cached=video_source_track.stop,
    )
    if is_new_track:
        _install_cached_with_shutdown_observer(
            session_state=session_state,
            cache_key=cache_key,
            observer_cache_key=observer_cache_key,
            cached=video_source_track,
            shutdown_callback=(
                reset_on_webrtc_session_end
                if lifecycle_scope == "webrtc-session"
                else video_source_track.stop
            ),
        )
    return video_source_track


_AUDIO_SOURCE_TRACK_CACHE_KEY_PREFIX = "__AUDIO_SOURCE_TRACK_CACHE__"
_AUDIO_SOURCE_TRACK_SHUTDOWN_OBSERVER_CACHE_KEY_PREFIX = (
    "__AUDIO_SOURCE_TRACK_SHUTDOWN_OBSERVER_CACHE__"
)


_VIDEO_SINK_TRACK_CACHE_KEY_PREFIX = "__VIDEO_SINK_TRACK_CACHE__"
_VIDEO_SINK_TRACK_SHUTDOWN_OBSERVER_CACHE_KEY_PREFIX = (
    "__VIDEO_SINK_TRACK_SHUTDOWN_OBSERVER_CACHE__"
)


def create_video_sink_track(
    callback: VideoSinkCallback,
    key: str,
    on_ended: Optional[Callable[[], None]] = None,
    lifecycle_scope: LifecycleScope = "webrtc-session",
) -> VideoSinkTrack:
    lifecycle_scope = _validate_lifecycle_scope(lifecycle_scope)
    session_state = _get_current_session_state()
    cache_key = _VIDEO_SINK_TRACK_CACHE_KEY_PREFIX + key
    observer_cache_key = _VIDEO_SINK_TRACK_SHUTDOWN_OBSERVER_CACHE_KEY_PREFIX + key
    is_new_track = False
    if (
        cache_key in session_state
        and isinstance(session_state[cache_key], VideoSinkTrack)
        and session_state[cache_key].readyState != "ended"
    ):
        video_sink_track: VideoSinkTrack = session_state[cache_key]
        video_sink_track._callback = callback
    else:
        video_sink_track = VideoSinkTrack(callback=callback)
        is_new_track = True
    video_sink_track._on_ended_callback = on_ended
    reset_on_webrtc_session_end = _attach_factory_lifecycle(
        session_state=session_state,
        cache_key=cache_key,
        observer_cache_key=observer_cache_key,
        lifecycle_target=video_sink_track,
        lifecycle_scope=lifecycle_scope,
        stop_cached=video_sink_track.stop,
    )
    if is_new_track:
        _install_cached_with_shutdown_observer(
            session_state=session_state,
            cache_key=cache_key,
            observer_cache_key=observer_cache_key,
            cached=video_sink_track,
            shutdown_callback=(
                reset_on_webrtc_session_end
                if lifecycle_scope == "webrtc-session"
                else video_sink_track.stop
            ),
        )
    return video_sink_track


_AUDIO_SINK_TRACK_CACHE_KEY_PREFIX = "__AUDIO_SINK_TRACK_CACHE__"
_AUDIO_SINK_TRACK_SHUTDOWN_OBSERVER_CACHE_KEY_PREFIX = (
    "__AUDIO_SINK_TRACK_SHUTDOWN_OBSERVER_CACHE__"
)


def create_audio_sink_track(
    callback: AudioSinkCallback,
    key: str,
    on_ended: Optional[Callable[[], None]] = None,
    lifecycle_scope: LifecycleScope = "webrtc-session",
) -> AudioSinkTrack:
    lifecycle_scope = _validate_lifecycle_scope(lifecycle_scope)
    session_state = _get_current_session_state()
    cache_key = _AUDIO_SINK_TRACK_CACHE_KEY_PREFIX + key
    observer_cache_key = _AUDIO_SINK_TRACK_SHUTDOWN_OBSERVER_CACHE_KEY_PREFIX + key
    is_new_track = False
    if (
        cache_key in session_state
        and isinstance(session_state[cache_key], AudioSinkTrack)
        and session_state[cache_key].readyState != "ended"
    ):
        audio_sink_track: AudioSinkTrack = session_state[cache_key]
        audio_sink_track._callback = callback
    else:
        audio_sink_track = AudioSinkTrack(callback=callback)
        is_new_track = True
    audio_sink_track._on_ended_callback = on_ended
    reset_on_webrtc_session_end = _attach_factory_lifecycle(
        session_state=session_state,
        cache_key=cache_key,
        observer_cache_key=observer_cache_key,
        lifecycle_target=audio_sink_track,
        lifecycle_scope=lifecycle_scope,
        stop_cached=audio_sink_track.stop,
    )
    if is_new_track:
        _install_cached_with_shutdown_observer(
            session_state=session_state,
            cache_key=cache_key,
            observer_cache_key=observer_cache_key,
            cached=audio_sink_track,
            shutdown_callback=(
                reset_on_webrtc_session_end
                if lifecycle_scope == "webrtc-session"
                else audio_sink_track.stop
            ),
        )
    return audio_sink_track


_PCM_AUDIO_SOURCE_CACHE_KEY_PREFIX = "__PCM_AUDIO_SOURCE_CACHE__"
_PCM_AUDIO_SOURCE_SHUTDOWN_OBSERVER_CACHE_KEY_PREFIX = (
    "__PCM_AUDIO_SOURCE_SHUTDOWN_OBSERVER_CACHE__"
)


def create_pcm_audio_source_track(
    *,
    key: str,
    sample_rate: int,
    ptime: float = 0.020,
    lifecycle_scope: LifecycleScope = "webrtc-session",
) -> PcmAudioSource:
    """Create a source track that plays s16-mono PCM pushed from any thread.

    Mirrors :func:`create_audio_source_track`'s key-based session cache so
    the buffer survives Streamlit reruns and queued audio isn't lost.

    The returned :class:`PcmAudioSource` exposes ``track`` (pass to
    ``webrtc_streamer(source_audio_track=...)``), :meth:`PcmAudioSource.push`
    (append PCM bytes / int16 ndarray, callable from any thread), and
    :meth:`PcmAudioSource.clear` (drop buffered samples, e.g. on barge-in).
    """
    lifecycle_scope = _validate_lifecycle_scope(lifecycle_scope)
    session_state = _get_current_session_state()
    cache_key = _PCM_AUDIO_SOURCE_CACHE_KEY_PREFIX + key
    observer_cache_key = _PCM_AUDIO_SOURCE_SHUTDOWN_OBSERVER_CACHE_KEY_PREFIX + key
    existing = session_state.get(cache_key)
    if (
        isinstance(existing, PcmAudioSource)
        and existing.track.readyState == "live"
        and existing.sample_rate == sample_rate
        and existing.ptime == ptime
    ):
        _attach_factory_lifecycle(
            session_state=session_state,
            cache_key=cache_key,
            observer_cache_key=observer_cache_key,
            lifecycle_target=existing.track,
            lifecycle_scope=lifecycle_scope,
            stop_cached=existing.track.stop,
        )
        return existing

    # Stopping the observer doesn't fire its callback, so if the cache held a
    # PcmAudioSource whose track is still live (param change between reruns),
    # stop it explicitly to avoid leaking the underlying media track.
    if isinstance(existing, PcmAudioSource) and existing.track.readyState == "live":
        existing.track.stop()

    pcm_source = PcmAudioSource(sample_rate=sample_rate, ptime=ptime)
    reset_on_webrtc_session_end = _attach_factory_lifecycle(
        session_state=session_state,
        cache_key=cache_key,
        observer_cache_key=observer_cache_key,
        lifecycle_target=pcm_source.track,
        lifecycle_scope=lifecycle_scope,
        stop_cached=pcm_source.track.stop,
    )
    _install_cached_with_shutdown_observer(
        session_state=session_state,
        cache_key=cache_key,
        observer_cache_key=observer_cache_key,
        cached=pcm_source,
        shutdown_callback=(
            reset_on_webrtc_session_end
            if lifecycle_scope == "webrtc-session"
            else pcm_source.track.stop
        ),
    )
    return pcm_source


def create_audio_source_track(
    callback: AudioSourceCallback,
    key: str,
    sample_rate: int = 48000,
    ptime: float = 0.020,
    on_ended: Optional[Callable[[], None]] = None,
    lifecycle_scope: LifecycleScope = "webrtc-session",
) -> AudioSourceTrack:
    lifecycle_scope = _validate_lifecycle_scope(lifecycle_scope)
    session_state = _get_current_session_state()
    cache_key = _AUDIO_SOURCE_TRACK_CACHE_KEY_PREFIX + key
    observer_cache_key = _AUDIO_SOURCE_TRACK_SHUTDOWN_OBSERVER_CACHE_KEY_PREFIX + key
    is_new_track = False
    if (
        cache_key in session_state
        and isinstance(session_state[cache_key], AudioSourceTrack)
        and session_state[cache_key].kind == "audio"
        and session_state[cache_key].readyState == "live"
    ):
        audio_source_track: AudioSourceTrack = session_state[cache_key]
        audio_source_track._callback = callback
        audio_source_track._sample_rate = sample_rate
        audio_source_track._ptime = ptime
        audio_source_track._samples_per_frame = int(sample_rate * ptime)
    else:
        audio_source_track = AudioSourceTrack(
            callback=callback, sample_rate=sample_rate, ptime=ptime
        )
        is_new_track = True
    audio_source_track._on_ended_callback = on_ended
    reset_on_webrtc_session_end = _attach_factory_lifecycle(
        session_state=session_state,
        cache_key=cache_key,
        observer_cache_key=observer_cache_key,
        lifecycle_target=audio_source_track,
        lifecycle_scope=lifecycle_scope,
        stop_cached=audio_source_track.stop,
    )
    if is_new_track:
        _install_cached_with_shutdown_observer(
            session_state=session_state,
            cache_key=cache_key,
            observer_cache_key=observer_cache_key,
            cached=audio_source_track,
            shutdown_callback=(
                reset_on_webrtc_session_end
                if lifecycle_scope == "webrtc-session"
                else audio_source_track.stop
            ),
        )
    return audio_source_track
