from typing import Callable, Generic, Hashable, TypeVar

import streamlit as st
from aiortc import MediaStreamTrack

from .eventloop import get_server_event_loop, loop_context
from .process import (
    AsyncAudioProcessTrack,
    AsyncMediaProcessTrack,
    AsyncVideoProcessTrack,
    ProcessorT,
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
) -> ObjectHashWrapper[AsyncMediaProcessTrack]:
    input_track = wrapped_input_track.obj
    processor_factory = wrapped_processor_factory.obj

    processor = processor_factory()

    if input_track.kind == "video":
        Track = AsyncVideoProcessTrack
    elif input_track.kind == "audio":
        # TODO: type checking
        Track = AsyncAudioProcessTrack  # type: ignore
    else:
        raise ValueError(f"Unsupported track type: {input_track.kind}")

    loop = get_server_event_loop()
    relay = get_relay(loop)
    output_track: MediaStreamTrack
    with loop_context(loop):
        # TODO: type checking
        output_track = Track(relay.subscribe(input_track), processor)  # type: ignore

    return ObjectHashWrapper(output_track, output_track.id)


def create_process_track(
    input_track: MediaStreamTrack, processor_factory: Callable[[], ProcessorT]
) -> AsyncMediaProcessTrack:
    wrapped_input_track = ObjectHashWrapper(input_track, input_track.id)
    wrapped_processor_factory = ObjectHashWrapper(processor_factory, None)
    wrapped_output_track = _inner_create_process_track(
        wrapped_input_track, wrapped_processor_factory
    )
    return wrapped_output_track.obj
