from typing import Optional, Union, overload

try:
    from typing import Literal
except ImportError:
    from typing_extensions import Literal  # type: ignore

import streamlit as st
from aiortc import MediaStreamTrack

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
from .process import (
    AsyncAudioProcessTrack,
    AsyncMediaProcessTrack,
    AsyncVideoProcessTrack,
    AudioProcessTrack,
    MediaProcessTrack,
    VideoProcessTrack,
)
from .relay import get_global_relay

_PROCESSOR_TRACK_CACHE_KEY_PREFIX = "__PROCESSOR_TRACK_CACHE__"


def _get_track_class(
    kind: Literal["video", "audio"], async_processing: bool
) -> MediaStreamTrack:
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
) -> AudioProcessTrack[AudioProcessorT]:
    ...


@overload
def create_process_track(
    input_track,
    *,
    processor_factory: AudioProcessorFactory[AudioProcessorT],
    async_processing: Literal[True] = True,
    frame_callback: Optional[FrameCallback] = None,
    queued_frames_callback: Optional[QueuedVideoFramesCallback] = None,
    on_ended: Optional[MediaEndedCallback] = None,
) -> AsyncAudioProcessTrack[AudioProcessorT]:
    ...


@overload
def create_process_track(
    input_track,
    *,
    processor_factory: VideoProcessorFactory[VideoProcessorT],
    async_processing: Literal[False],
    frame_callback: Optional[FrameCallback] = None,
    queued_frames_callback: Optional[QueuedVideoFramesCallback] = None,
    on_ended: Optional[MediaEndedCallback] = None,
) -> VideoProcessTrack[VideoProcessorT]:
    ...


@overload
def create_process_track(
    input_track,
    *,
    processor_factory: VideoProcessorFactory[VideoProcessorT],
    async_processing: Literal[True] = True,
    frame_callback: Optional[FrameCallback] = None,
    queued_frames_callback: Optional[QueuedVideoFramesCallback] = None,
    on_ended: Optional[MediaEndedCallback] = None,
) -> AsyncVideoProcessTrack[VideoProcessorT]:
    ...


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
) -> MediaProcessTrack[CallbackAttachableProcessor[FrameT], FrameT]:
    ...


@overload
def create_process_track(
    input_track,
    *,
    frame_callback: FrameCallback[FrameT],
    processor_factory: Literal[None] = None,
    async_processing: Literal[True] = True,
    queued_frames_callback: Optional[QueuedVideoFramesCallback] = None,
    on_ended: Optional[MediaEndedCallback] = None,
) -> AsyncMediaProcessTrack[CallbackAttachableProcessor[FrameT], FrameT]:
    ...


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
