from typing import Generic, Hashable, TypeVar, Union, overload

try:
    from typing import Literal
except ImportError:
    from typing_extensions import Literal  # type: ignore

import streamlit as st
from aiortc import MediaStreamTrack

from .eventloop import get_server_event_loop, loop_context
from .mix import MediaStreamMixTrack, MixerCallback
from .models import FrameT
from .process import (
    AsyncAudioProcessTrack,
    AsyncMediaProcessTrack,
    AsyncVideoProcessTrack,
    AudioProcessTrack,
    MediaProcessTrack,
    VideoProcessTrack,
)
from .relay import get_global_relay
from .webrtc import (
    AudioProcessorFactory,
    AudioProcessorT,
    VideoProcessorFactory,
    VideoProcessorT,
)

HashedObjT = TypeVar("HashedObjT")


# NOTE: Workaround of dealing with hash_funcs of st.cache.
# See https://discuss.streamlit.io/t/how-to-specify-hash-funcs-of-st-cache-for-all-subtypes-of-a-specific-class/14535  # noqa: E501
class ObjectHashWrapper(Generic[HashedObjT]):
    def __init__(self, obj: HashedObjT, hash: Hashable) -> None:
        self.obj = obj
        self.hash = hash


@st.cache(hash_funcs={ObjectHashWrapper: lambda o: o.hash})
def _inner_create_process_track(
    wrapped_input_track: ObjectHashWrapper[MediaStreamTrack],
    wrapped_processor_factory: ObjectHashWrapper[
        Union[VideoProcessorFactory, AudioProcessorFactory]
    ],
    async_processing: bool,
) -> ObjectHashWrapper[Union[AsyncMediaProcessTrack, MediaProcessTrack]]:
    input_track = wrapped_input_track.obj
    processor_factory = wrapped_processor_factory.obj

    processor = processor_factory()

    Track: MediaStreamTrack
    if input_track.kind == "video":
        if async_processing:
            Track = AsyncVideoProcessTrack
        else:
            Track = VideoProcessTrack
    elif input_track.kind == "audio":
        if async_processing:
            Track = AsyncAudioProcessTrack
        else:
            Track = AudioProcessTrack
    else:
        raise ValueError(f"Unsupported track type: {input_track.kind}")

    loop = get_server_event_loop()
    relay = get_global_relay()
    with loop_context(loop):
        output_track = Track(relay.subscribe(input_track), processor)

    return ObjectHashWrapper(output_track, output_track.id)


@overload
def create_process_track(
    input_track: MediaStreamTrack,
    processor_factory: VideoProcessorFactory[VideoProcessorT],
    async_processing: Literal[True] = True,
) -> AsyncVideoProcessTrack[VideoProcessorT]:
    pass


@overload
def create_process_track(
    input_track: MediaStreamTrack,
    processor_factory: VideoProcessorFactory[VideoProcessorT],
    async_processing: Literal[False],
) -> VideoProcessTrack[VideoProcessorT]:
    pass


@overload
def create_process_track(
    input_track: MediaStreamTrack,
    processor_factory: AudioProcessorFactory[AudioProcessorT],
    async_processing: Literal[True] = True,
) -> AsyncAudioProcessTrack[AudioProcessorT]:
    pass


@overload
def create_process_track(
    input_track: MediaStreamTrack,
    processor_factory: AudioProcessorFactory[AudioProcessorT],
    async_processing: Literal[False],
) -> AudioProcessTrack[AudioProcessorT]:
    pass


def create_process_track(
    input_track,
    processor_factory,
    async_processing=True,
):
    wrapped_input_track = ObjectHashWrapper(input_track, input_track.id)
    wrapped_processor_factory = ObjectHashWrapper(processor_factory, None)
    wrapped_output_track = _inner_create_process_track(
        wrapped_input_track, wrapped_processor_factory, async_processing
    )
    return wrapped_output_track.obj


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
