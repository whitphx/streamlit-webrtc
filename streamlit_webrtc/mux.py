import abc
import asyncio
import functools
import logging
import threading
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


class InputQueieItem(NamedTuple):
    source_track_obj_id: int
    frame: Optional[Frame]


async def input_track_coro(input_track: MediaStreamTrack, queue: asyncio.Queue):
    source_track_obj_id = input_track.id
    while True:
        try:
            frame = await input_track.recv()
        except MediaStreamError:
            frame = None
        queue.put_nowait(
            InputQueieItem(source_track_obj_id=source_track_obj_id, frame=frame)
        )
        if frame is None:
            break


async def gather_frames_coro(muxer: "MediaStreamMuxTrack"):
    latest_frames_map: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()

    while True:
        try:
            item: InputQueieItem = await muxer._input_queue.get()
        except MediaStreamError:
            return

        source_track = None
        with muxer._input_proxies_lock:
            for proxy in muxer._input_proxies.values():
                if proxy.id == item.source_track_obj_id:
                    source_track = proxy
            if source_track is None:
                LOGGER.warning("Source track not found")
                continue

            frame = item.frame
            latest_frames_map[source_track] = frame

            latest_frames = [
                latest_frames_map.get(proxy)
                for proxy in muxer._input_proxies.values()
                if proxy.readyState == "live"
            ]
            muxer._set_latest_frames(latest_frames)


async def mux_coro(muxer: "MediaStreamMuxTrack"):
    while True:
        latest_frames = await muxer._get_latest_frames()  # Wait for new frames arrive
        output_frame = muxer.on_update(latest_frames)
        muxer._queue.put_nowait(output_frame)


class MediaStreamMuxTrack(MediaStreamTrack):
    kind: str

    _loop: asyncio.AbstractEventLoop
    _input_proxies_lock: threading.Lock
    _input_proxies: "OrderedDict[MediaStreamTrack, RelayStreamTrack]"
    _input_queue: asyncio.Queue
    _queue: asyncio.Queue
    _latest_frames: List[Frame]
    _mux_control_queue: asyncio.Queue

    _gather_frames_task: Union[asyncio.Task, None]
    _mux_task: Union[asyncio.Task, None]

    def __init__(self) -> None:
        if not self.kind:
            raise NotImplementedError("kind must be set")

        loop = get_server_event_loop()

        with loop_context(loop):
            super().__init__()
            self._queue: asyncio.Queue[Optional[av.Frame]] = asyncio.Queue()

            self._input_proxies = OrderedDict()
            self._input_proxies_lock = threading.Lock()

            self._input_queue = asyncio.Queue()

            self._latest_frames = []

            self._mux_control_queue = asyncio.Queue()

            self._loop = loop

            self._gather_frames_task = None
            self._mux_task = None

    def _start(self):
        if not self._gather_frames_task:
            self._gather_frames_task = self._loop.create_task(
                gather_frames_coro(muxer=self)
            )
        if not self._mux_task:
            self._mux_task = self._loop.create_task(mux_coro(muxer=self))

    def add_input_track(self, input_track: MediaStreamTrack) -> None:
        LOGGER.debug("Add a track %s to %s", input_track, self)

        with self._input_proxies_lock:
            if input_track in self._input_proxies:
                return

            relay = get_relay(self._loop)
            with loop_context(self._loop):
                input_proxy = relay.subscribe(input_track)

            self._input_proxies[input_track] = input_proxy

        self._loop.create_task(
            input_track_coro(input_track=input_proxy, queue=self._input_queue)
        )

        input_proxy.on("ended")(functools.partial(self.remove_input_proxy, input_proxy))

    def remove_input_proxy(self, input_proxy: RelayStreamTrack) -> None:
        LOGGER.debug("Remove a relay track %s from %s", input_proxy, self)
        with self._input_proxies_lock:
            self._input_proxies.popitem(input_proxy)

    def _set_latest_frames(self, latest_frames: List[Frame]):
        # with self._latest_frames_lock:
        if self._mux_control_queue.qsize() == 0:
            self._mux_control_queue.put_nowait(True)
        self._latest_frames = latest_frames

    async def _get_latest_frames(self) -> List[Frame]:
        await self._mux_control_queue.get()
        return self._latest_frames

    @abc.abstractmethod
    def on_update(self, frames: List[Frame]) -> Frame:
        pass

    async def recv(self):
        if self.readyState != "live":
            raise MediaStreamError

        self._start()

        frame = await self._queue.get()
        if frame is None:
            self.stop()
            raise MediaStreamError
        return frame
