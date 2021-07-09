import abc
import asyncio
import functools
import logging
import sys
import threading
import traceback
import weakref
from collections import OrderedDict
from typing import List, NamedTuple, Optional, Union

import av
from aiortc import MediaStreamTrack
from aiortc.contrib.media import RelayStreamTrack
from aiortc.mediastreams import MediaStreamError

from .eventloop import get_server_event_loop, loop_context
from .relay import get_relay

LOGGER = logging.getLogger(__name__)


Frame = Union[av.VideoFrame, av.AudioFrame]


class MuxerBase(abc.ABC):
    @abc.abstractmethod
    def on_update(self, frames: List[Frame]) -> Frame:
        """
        Receives frames from input tracks and returns one frame to output.
        """


class InputQueueItem(NamedTuple):
    source_track_id: int
    frame: Optional[Frame]


async def input_track_coro(
    input_track: RelayStreamTrack, mux_track: "MediaStreamMuxTrack"
):
    source_track_id = input_track.id
    while True:
        try:
            frame = await input_track.recv()
        except MediaStreamError:
            frame = None
        if mux_track._output_started:
            mux_track._input_queue.put_nowait(
                InputQueueItem(source_track_id=source_track_id, frame=frame)
            )
        if frame is None:
            break


async def gather_frames_coro(mux_track: "MediaStreamMuxTrack"):
    while True:
        try:
            item: InputQueueItem = await mux_track._input_queue.get()
        except MediaStreamError:
            LOGGER.warning("Stop gather_frames_coro")
            mux_track.stop()
            return

        source_track = None
        with mux_track._input_proxies_lock:
            for proxy in mux_track._input_proxies.values():
                if proxy.id == item.source_track_id:
                    source_track = proxy
            if source_track is None:
                LOGGER.warning("Source track not found")
                continue

        frame = item.frame
        mux_track._set_latest_frame(source_track, frame)


async def mux_coro(mux_track: "MediaStreamMuxTrack"):
    while True:
        latest_frames = (
            await mux_track._get_latest_frames()
        )  # Wait for new frames arrive
        try:
            output_frame = mux_track.muxer.on_update(latest_frames)
        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            for tb in traceback.format_exception(exc_type, exc_value, exc_traceback):
                for tbline in tb.rstrip().splitlines():
                    LOGGER.error(tbline.rstrip())
        mux_track._queue.put_nowait(output_frame)


class MediaStreamMuxTrack(MediaStreamTrack):
    kind: str
    muxer: MuxerBase

    _loop: asyncio.AbstractEventLoop
    _input_proxies_lock: threading.Lock
    _input_proxies: "OrderedDict[MediaStreamTrack, RelayStreamTrack]"
    _input_tasks: "weakref.WeakKeyDictionary[RelayStreamTrack, asyncio.Task]"
    _input_queue: asyncio.Queue
    _queue: "asyncio.Queue[Optional[Frame]]"
    _latest_frames_map: "weakref.WeakKeyDictionary[RelayStreamTrack, Union[Frame, None]]"  # noqa: E501
    _latest_frames_updated_event: asyncio.Event

    _output_started: bool

    _gather_frames_task: Union[asyncio.Task, None]
    _mux_task: Union[asyncio.Task, None]

    def __init__(self, kind: str, muxer: MuxerBase) -> None:
        self.kind = kind
        self.muxer = muxer

        loop = get_server_event_loop()

        with loop_context(loop):
            super().__init__()

            self._queue = asyncio.Queue()

            self._input_proxies = OrderedDict()
            self._input_proxies_lock = threading.Lock()

            self._input_tasks = weakref.WeakKeyDictionary()

            self._input_queue = asyncio.Queue()

            self._latest_frames_map = weakref.WeakKeyDictionary()

            self._latest_frames_updated_event = asyncio.Event()

            self._loop = loop

            self._gather_frames_task = None
            self._mux_task = None

            self._output_started = False

    def _start(self):
        if self._output_started:
            return

        self._gather_frames_task = self._loop.create_task(
            gather_frames_coro(mux_track=self)
        )
        self._mux_task = self._loop.create_task(mux_coro(mux_track=self))

        self._output_started = True

    def stop(self):
        super().stop()

        if self._gather_frames_task:
            self._gather_frames_task.cancel()
            self._gather_frames_task = None
        if self._mux_task:
            self._mux_task.cancel()
            self._mux_task = None

    def add_input_track(self, input_track: MediaStreamTrack) -> None:
        LOGGER.debug("Add a track %s to %s", input_track, self)

        with self._input_proxies_lock:
            if input_track in self._input_proxies:
                return

            relay = get_relay(self._loop)
            with loop_context(self._loop):
                input_proxy = relay.subscribe(input_track)

            self._input_proxies[input_track] = input_proxy

        LOGGER.debug(
            "A proxy %s subscribing %s is added to %s", input_proxy, input_track, self
        )

        task = self._loop.create_task(
            input_track_coro(input_track=input_proxy, mux_track=self)
        )
        self._input_tasks[input_proxy] = task

        input_proxy.on("ended")(functools.partial(self.remove_input_proxy, input_proxy))

    def remove_input_proxy(self, input_proxy: RelayStreamTrack) -> None:
        LOGGER.debug("Remove a relay track %s from %s", input_proxy, self)
        with self._input_proxies_lock:
            del_key = None
            for key, value in self._input_proxies.items():
                if value == input_proxy:
                    del_key = key
            if del_key:
                self._input_proxies.pop(del_key)

        self._latest_frames_map.pop(input_proxy)

        task = self._input_tasks.pop(input_proxy)
        task.cancel()

    def _set_latest_frame(
        self, input_proxy: RelayStreamTrack, frame: Union[Frame, None]
    ):
        # TODO: Lock here to make these 2 lines atomic
        self._latest_frames_map[input_proxy] = frame
        self._latest_frames_updated_event.set()

    async def _get_latest_frames(self) -> List[Frame]:
        # TODO: Lock here to make these 2 lines atomic
        await self._latest_frames_updated_event.wait()
        self._latest_frames_updated_event.clear()

        with self._input_proxies_lock:
            latest_frames = [
                self._latest_frames_map.get(proxy)
                for proxy in self._input_proxies.values()
            ]
        latest_frames = [f for f in latest_frames if f is not None]
        return latest_frames

    async def recv(self):
        if self.readyState != "live":
            raise MediaStreamError

        self._start()

        frame = await self._queue.get()
        if frame is None:
            self.stop()
            raise MediaStreamError
        return frame
