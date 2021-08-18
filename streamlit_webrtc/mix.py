import asyncio
import fractions
import functools
import logging
import sys
import threading
import time
import traceback
import weakref
from collections import OrderedDict
from typing import Generic, Union

import av
from aiortc import MediaStreamTrack
from aiortc.contrib.media import RelayStreamTrack
from aiortc.mediastreams import MediaStreamError

from .eventloop import get_server_event_loop, loop_context
from .relay import get_global_relay
from .types import MixerBase, MixerT

__all__ = [
    "MixerBase",
    "MediaStreamMixTrack",
]


LOGGER = logging.getLogger(__name__)


# Simply widely-used values are chosen here, but without any strict reasons.
# Ref: https://github.com/aiortc/aiortc/blob/main/src/aiortc/mediastreams.py
AUDIO_SAMPLE_RATE = 48000
AUDIO_TIME_BASE = fractions.Fraction(1, AUDIO_SAMPLE_RATE)
VIDEO_CLOCK_RATE = 90000
VIDEO_TIME_BASE = fractions.Fraction(1, VIDEO_CLOCK_RATE)


Frame = Union[av.VideoFrame, av.AudioFrame]


__SENTINEL__ = "__SENTINEL__"


class MediaStreamMixTrack(MediaStreamTrack, Generic[MixerT]):
    _input_tasks: "weakref.WeakKeyDictionary[RelayStreamTrack, asyncio.Task]"
    _input_proxies_lock: threading.Lock
    _input_proxies: "OrderedDict[MediaStreamTrack, RelayStreamTrack]"
    _latest_frames_map: "weakref.WeakKeyDictionary[RelayStreamTrack, Union[Frame, None]]"  # noqa: E501
    _input_event: asyncio.Event
    _mixer_input_queue: asyncio.Queue
    _mixer_output_queue: asyncio.Queue
    _mixer_task: asyncio.Task
    _loop: asyncio.AbstractEventLoop

    def __init__(self, kind: str, mixer: MixerT) -> None:
        super().__init__()

        self.kind = kind
        self.mixer = mixer

        # self._loop = asyncio.new_event_loop()
        self._loop = get_server_event_loop()
        self._input_tasks = weakref.WeakKeyDictionary()
        self._input_proxies = OrderedDict()
        self._input_proxies_lock = threading.Lock()
        self._latest_frames_map = weakref.WeakKeyDictionary()
        self._mixer_task = None

        with loop_context(self._loop):
            self._input_event = asyncio.Event()

    def _start(self):
        if self._mixer_task:
            return

        self._mixer_input_queue = asyncio.Queue()
        self._mixer_output_queue = asyncio.Queue()
        self._mixer_task = asyncio.ensure_future(self._mixer_coro(), loop=self._loop)

    def stop(self):
        super().stop()

        for track in self._input_proxies.values():
            track.stop()

    def add_input_track(self, input_track: MediaStreamTrack) -> None:
        LOGGER.debug("Add a track %s to %s", input_track, self)

        with self._input_proxies_lock:
            if input_track in self._input_proxies:
                return

            relay = get_global_relay()
            with loop_context(self._loop):
                input_proxy = relay.subscribe(input_track)

            self._input_proxies[input_track] = input_proxy

        LOGGER.debug(
            "A proxy %s subscribing %s is added to %s", input_proxy, input_track, self
        )

        task = asyncio.ensure_future(self.__run_track(input_proxy), loop=self._loop)
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

    async def __run_track(self, track: RelayStreamTrack):
        while True:
            try:
                frame = await track.recv()
                self._input_event.set()
            except MediaStreamError:
                return
            self._latest_frames_map[track] = frame

    async def _mixer_coro(self):
        started_at = time.monotonic()

        while True:
            item = await self._mixer_input_queue.get()

            queued_items = [item]

            stop_requested = False
            while not self._mixer_input_queue.empty():
                item = self._mixer_input_queue.get_nowait()
                if item == __SENTINEL__:
                    stop_requested = True
                    break
                else:
                    queued_items.append(item)
            if stop_requested:
                break

            if len(queued_items) == 0:
                raise Exception("Unexpectedly, queued frames do not exist")

            # Set up a future, providing the frames.
            latest_frames = queued_items[-1]  # TODO: Make use of all queue items

            try:
                output_frame = self.mixer.on_update(latest_frames)

                if output_frame.pts is None and output_frame.time_base is None:
                    timestamp = time.monotonic() - started_at
                    if isinstance(output_frame, av.VideoFrame):
                        output_frame.pts = timestamp * VIDEO_CLOCK_RATE
                        output_frame.time_base = VIDEO_TIME_BASE
                    elif isinstance(output_frame, av.AudioFrame):
                        output_frame.pts = timestamp * AUDIO_SAMPLE_RATE
                        output_frame.time_base = AUDIO_TIME_BASE

            except Exception:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                for tb in traceback.format_exception(
                    exc_type, exc_value, exc_traceback
                ):
                    for tbline in tb.rstrip().splitlines():
                        LOGGER.error(tbline.rstrip())

            await self._mixer_output_queue.put(output_frame)

    async def recv(self):
        if self.readyState != "live":
            raise MediaStreamError

        self._start()

        await asyncio.sleep(
            0.5
        )  # TODO: Be configurable / set appropriate value automatically.
        # NOTE: 出力の数が増えるとおそらくencodeが詰まって遅くなるので、その前段たるこの段階で適宜throttleするadhoc対応。

        await self._input_event.wait()
        self._input_event.clear()

        input_frames = list(self._latest_frames_map.values())

        self._mixer_input_queue.put_nowait(input_frames)

        new_frame = await self._mixer_output_queue.get()

        return new_frame
