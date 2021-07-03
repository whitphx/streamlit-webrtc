from typing import Callable, Generic, Hashable, TypeVar, overload

try:
    from typing import Literal
except ImportError:
    from typing_extensions import Literal  # type: ignore

import streamlit as st
from aiortc import MediaStreamTrack

from .eventloop import get_server_event_loop, loop_context
from .process import (
    AsyncAudioProcessTrack,
    AsyncMediaProcessTrack,
    AsyncVideoProcessTrack,
    AudioProcessorBase,
    AudioProcessTrack,
    ProcessorT,
    VideoProcessorBase,
    VideoProcessTrack,
)
from .relay import get_relay

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
    wrapped_processor_factory: ObjectHashWrapper[Callable[[], ProcessorT]],
    async_processing: bool,
) -> ObjectHashWrapper[AsyncMediaProcessTrack]:
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
    relay = get_relay(loop)
    output_track: MediaStreamTrack
    with loop_context(loop):
        output_track = Track(relay.subscribe(input_track), processor)  # type: ignore

    return ObjectHashWrapper(output_track, output_track.id)


@overload
def create_process_track(
    input_track: MediaStreamTrack,
    processor_factory: Callable[[], VideoProcessorBase],
    async_processing: Literal[True],
) -> AsyncVideoProcessTrack:
    pass


@overload
def create_process_track(
    input_track: MediaStreamTrack,
    processor_factory: Callable[[], VideoProcessorBase],
    async_processing: Literal[False],
) -> VideoProcessTrack:
    pass


@overload
def create_process_track(
    input_track: MediaStreamTrack,
    processor_factory: Callable[[], AudioProcessorBase],
    async_processing: Literal[True],
) -> AsyncAudioProcessTrack:
    pass


@overload
def create_process_track(
    input_track: MediaStreamTrack,
    processor_factory: Callable[[], AudioProcessorBase],
    async_processing: Literal[False],
) -> AudioProcessTrack:
    pass


def create_process_track(
    input_track: MediaStreamTrack,
    processor_factory: Callable[[], ProcessorT],
    async_processing: bool = True,
) -> MediaStreamTrack:
    wrapped_input_track = ObjectHashWrapper(input_track, input_track.id)
    wrapped_processor_factory = ObjectHashWrapper(processor_factory, None)
    wrapped_output_track = _inner_create_process_track(
        wrapped_input_track, wrapped_processor_factory, async_processing
    )
    return wrapped_output_track.obj
