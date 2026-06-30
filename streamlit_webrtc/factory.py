from typing import Any, Callable, Literal, Optional, Type, Union, overload

import streamlit as st

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
ResetKey = Union[int, str]
_DEFAULT_RESET_KEY_SESSION_STATE_KEY = "__FACTORY_DEFAULT_RESET_KEY__"


def set_default_factory_reset_key(
    reset_key: Optional[ResetKey],
) -> None:
    """Set the default reset key for source/sink factory helpers.

    The default is scoped to the current Streamlit session. Factory helpers use
    it when their per-call ``reset_key`` argument is ``None``. Passing ``None``
    to this function clears the default and restores the legacy key-only cache
    behavior.
    """
    if reset_key is None:
        st.session_state.pop(_DEFAULT_RESET_KEY_SESSION_STATE_KEY, None)
    else:
        st.session_state[_DEFAULT_RESET_KEY_SESSION_STATE_KEY] = reset_key


def _resolve_reset_key(
    reset_key: Optional[ResetKey],
) -> Optional[ResetKey]:
    if reset_key is None:
        return st.session_state.get(_DEFAULT_RESET_KEY_SESSION_STATE_KEY, None)
    return reset_key


def _make_reset_cache_key(
    prefix: str,
    key: str,
    reset_key: Optional[ResetKey],
) -> str:
    if reset_key is None:
        return prefix + key
    return (
        prefix
        + key
        + f"__RESET_KEY__{type(reset_key).__name__}:"
        + str(reset_key)
    )


def _active_cache_key(prefix: str, key: str) -> str:
    return prefix + "__ACTIVE_CACHE_KEY__" + key


def _prepare_reset_cache(
    *,
    cache_prefix: str,
    observer_prefix: str,
    key: str,
    reset_key: Optional[ResetKey],
    stop_cached: Callable[[Any], None],
) -> tuple[str, str]:
    reset_key = _resolve_reset_key(reset_key)
    cache_key = _make_reset_cache_key(cache_prefix, key, reset_key)
    observer_cache_key = _make_reset_cache_key(observer_prefix, key, reset_key)

    active_cache_key = _active_cache_key(cache_prefix, key)
    active_observer_cache_key = _active_cache_key(observer_prefix, key)
    previous_cache_key = st.session_state.get(active_cache_key, cache_prefix + key)
    previous_observer_cache_key = st.session_state.get(
        active_observer_cache_key, observer_prefix + key
    )

    if previous_cache_key != cache_key:
        previous_observer = st.session_state.pop(previous_observer_cache_key, None)
        if isinstance(previous_observer, SessionShutdownObserver):
            previous_observer.stop()

        previous_cached = st.session_state.pop(previous_cache_key, None)
        if previous_cached is not None:
            stop_cached(previous_cached)

    st.session_state[active_cache_key] = cache_key
    st.session_state[active_observer_cache_key] = observer_cache_key
    return cache_key, observer_cache_key


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
    reset_key: Optional[ResetKey] = None,
) -> VideoSourceTrack:
    cache_key, observer_cache_key = _prepare_reset_cache(
        cache_prefix=_VIDEO_SOURCE_TRACK_CACHE_KEY_PREFIX,
        observer_prefix=_VIDEO_SOURCE_TRACK_SHUTDOWN_OBSERVER_CACHE_KEY_PREFIX,
        key=key,
        reset_key=reset_key,
        stop_cached=lambda track: track.stop(),
    )
    if (
        cache_key in st.session_state
        and isinstance(st.session_state[cache_key], VideoSourceTrack)
        and st.session_state[cache_key].kind == "video"
        and st.session_state[cache_key].readyState == "live"
    ):
        video_source_track: VideoSourceTrack = st.session_state[cache_key]
        video_source_track._callback = callback
        video_source_track._fps = fps
    else:
        # The previous observer (if any) is bound to a now-stopped track; stop
        # it before installing a fresh one so its polling thread isn't leaked
        # for the rest of the session.
        old_observer = st.session_state.get(observer_cache_key)
        if isinstance(old_observer, SessionShutdownObserver):
            old_observer.stop()

        video_source_track = VideoSourceTrack(callback=callback, fps=fps)
        st.session_state[cache_key] = video_source_track
        # Auto-stop on Streamlit session shutdown so the "ended" event (and
        # any `on_ended` callback) fires deterministically even when the user
        # closes the page without clicking the STOP button first.
        st.session_state[observer_cache_key] = SessionShutdownObserver(
            video_source_track.stop
        )
    video_source_track._on_ended_callback = on_ended
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
    reset_key: Optional[ResetKey] = None,
) -> VideoSinkTrack:
    cache_key, observer_cache_key = _prepare_reset_cache(
        cache_prefix=_VIDEO_SINK_TRACK_CACHE_KEY_PREFIX,
        observer_prefix=_VIDEO_SINK_TRACK_SHUTDOWN_OBSERVER_CACHE_KEY_PREFIX,
        key=key,
        reset_key=reset_key,
        stop_cached=lambda track: track.stop(),
    )
    if (
        cache_key in st.session_state
        and isinstance(st.session_state[cache_key], VideoSinkTrack)
        and st.session_state[cache_key].readyState != "ended"
    ):
        video_sink_track: VideoSinkTrack = st.session_state[cache_key]
        video_sink_track._callback = callback
    else:
        old_observer = st.session_state.get(observer_cache_key)
        if isinstance(old_observer, SessionShutdownObserver):
            old_observer.stop()

        video_sink_track = VideoSinkTrack(callback=callback)
        st.session_state[cache_key] = video_sink_track
        st.session_state[observer_cache_key] = SessionShutdownObserver(
            video_sink_track.stop
        )
    video_sink_track._on_ended_callback = on_ended
    return video_sink_track


_AUDIO_SINK_TRACK_CACHE_KEY_PREFIX = "__AUDIO_SINK_TRACK_CACHE__"
_AUDIO_SINK_TRACK_SHUTDOWN_OBSERVER_CACHE_KEY_PREFIX = (
    "__AUDIO_SINK_TRACK_SHUTDOWN_OBSERVER_CACHE__"
)


def create_audio_sink_track(
    callback: AudioSinkCallback,
    key: str,
    on_ended: Optional[Callable[[], None]] = None,
    reset_key: Optional[ResetKey] = None,
) -> AudioSinkTrack:
    cache_key, observer_cache_key = _prepare_reset_cache(
        cache_prefix=_AUDIO_SINK_TRACK_CACHE_KEY_PREFIX,
        observer_prefix=_AUDIO_SINK_TRACK_SHUTDOWN_OBSERVER_CACHE_KEY_PREFIX,
        key=key,
        reset_key=reset_key,
        stop_cached=lambda track: track.stop(),
    )
    if (
        cache_key in st.session_state
        and isinstance(st.session_state[cache_key], AudioSinkTrack)
        and st.session_state[cache_key].readyState != "ended"
    ):
        audio_sink_track: AudioSinkTrack = st.session_state[cache_key]
        audio_sink_track._callback = callback
    else:
        old_observer = st.session_state.get(observer_cache_key)
        if isinstance(old_observer, SessionShutdownObserver):
            old_observer.stop()

        audio_sink_track = AudioSinkTrack(callback=callback)
        st.session_state[cache_key] = audio_sink_track
        st.session_state[observer_cache_key] = SessionShutdownObserver(
            audio_sink_track.stop
        )
    audio_sink_track._on_ended_callback = on_ended
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
    reset_key: Optional[ResetKey] = None,
) -> PcmAudioSource:
    """Create a source track that plays s16-mono PCM pushed from any thread.

    Mirrors :func:`create_audio_source_track`'s key-based session cache so
    the buffer survives Streamlit reruns and queued audio isn't lost.

    The returned :class:`PcmAudioSource` exposes ``track`` (pass to
    ``webrtc_streamer(source_audio_track=...)``), :meth:`PcmAudioSource.push`
    (append PCM bytes / int16 ndarray, callable from any thread), and
    :meth:`PcmAudioSource.clear` (drop buffered samples, e.g. on barge-in).
    """
    cache_key, observer_cache_key = _prepare_reset_cache(
        cache_prefix=_PCM_AUDIO_SOURCE_CACHE_KEY_PREFIX,
        observer_prefix=_PCM_AUDIO_SOURCE_SHUTDOWN_OBSERVER_CACHE_KEY_PREFIX,
        key=key,
        reset_key=reset_key,
        stop_cached=lambda source: source.track.stop(),
    )
    existing = st.session_state.get(cache_key)
    if (
        isinstance(existing, PcmAudioSource)
        and existing.track.readyState == "live"
        and existing.sample_rate == sample_rate
        and existing.ptime == ptime
    ):
        return existing

    old_observer = st.session_state.get(observer_cache_key)
    if isinstance(old_observer, SessionShutdownObserver):
        old_observer.stop()
    # Stopping the observer doesn't fire its callback, so if the cache held a
    # PcmAudioSource whose track is still live (param change between reruns),
    # stop it explicitly to avoid leaking the underlying media track.
    if isinstance(existing, PcmAudioSource) and existing.track.readyState == "live":
        existing.track.stop()

    pcm_source = PcmAudioSource(sample_rate=sample_rate, ptime=ptime)
    st.session_state[cache_key] = pcm_source
    st.session_state[observer_cache_key] = SessionShutdownObserver(
        pcm_source.track.stop
    )
    return pcm_source


def create_audio_source_track(
    callback: AudioSourceCallback,
    key: str,
    sample_rate: int = 48000,
    ptime: float = 0.020,
    on_ended: Optional[Callable[[], None]] = None,
    reset_key: Optional[ResetKey] = None,
) -> AudioSourceTrack:
    cache_key, observer_cache_key = _prepare_reset_cache(
        cache_prefix=_AUDIO_SOURCE_TRACK_CACHE_KEY_PREFIX,
        observer_prefix=_AUDIO_SOURCE_TRACK_SHUTDOWN_OBSERVER_CACHE_KEY_PREFIX,
        key=key,
        reset_key=reset_key,
        stop_cached=lambda track: track.stop(),
    )
    if (
        cache_key in st.session_state
        and isinstance(st.session_state[cache_key], AudioSourceTrack)
        and st.session_state[cache_key].kind == "audio"
        and st.session_state[cache_key].readyState == "live"
    ):
        audio_source_track: AudioSourceTrack = st.session_state[cache_key]
        audio_source_track._callback = callback
        audio_source_track._sample_rate = sample_rate
        audio_source_track._ptime = ptime
        audio_source_track._samples_per_frame = int(sample_rate * ptime)
    else:
        old_observer = st.session_state.get(observer_cache_key)
        if isinstance(old_observer, SessionShutdownObserver):
            old_observer.stop()

        audio_source_track = AudioSourceTrack(
            callback=callback, sample_rate=sample_rate, ptime=ptime
        )
        st.session_state[cache_key] = audio_source_track
        st.session_state[observer_cache_key] = SessionShutdownObserver(
            audio_source_track.stop
        )
    audio_source_track._on_ended_callback = on_ended
    return audio_source_track
