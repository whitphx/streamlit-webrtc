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
from typing import Callable, Generic, List, NamedTuple, Optional, Union, cast

import av
from aiortc import MediaStreamTrack
from aiortc.contrib.media import RelayStreamTrack
from aiortc.mediastreams import MediaStreamError
from av.frame import Frame
from av.packet import Packet

from .eventloop import get_global_event_loop, loop_context
from .models import FrameT
from .relay import get_global_relay

__all__ = [
    "MixerCallback",
    "MediaStreamMixTrack",
]


LOGGER = logging.getLogger(__name__)


# Simply widely-used values are chosen here, but without any strict reasons.
# Ref: https://github.com/aiortc/aiortc/blob/main/src/aiortc/mediastreams.py
AUDIO_SAMPLE_RATE = 48000
AUDIO_TIME_BASE = fractions.Fraction(1, AUDIO_SAMPLE_RATE)
VIDEO_CLOCK_RATE = 90000
VIDEO_TIME_BASE = fractions.Fraction(1, VIDEO_CLOCK_RATE)


MixerCallback = Callable[[List[FrameT]], FrameT]


class InputQueueItem(NamedTuple):
    source_track_id: str
    frame: Optional[Union[Frame, Packet]]


async def input_track_coro(
    input_track: RelayStreamTrack, mix_track: "MediaStreamMixTrack"
):
    source_track_id = input_track.id
    while True:
        try:
            frame = await input_track.recv()
        except MediaStreamError:
            frame = None
        if mix_track._output_started:
            mix_track._input_queue.put_nowait(
                InputQueueItem(source_track_id=source_track_id, frame=frame)
            )
        if frame is None:
            break


async def gather_frames_coro(mix_track: "MediaStreamMixTrack"):
    while True:
        try:
            item: InputQueueItem = await mix_track._input_queue.get()
        except MediaStreamError:
            LOGGER.warning("Stop gather_frames_coro")
            mix_track.stop()
            return

        source_track = None
        with mix_track._input_proxies_lock:
            for proxy in mix_track._input_proxies.values():
                if proxy.id == item.source_track_id:
                    source_track = proxy
            if source_track is None:
                LOGGER.warning("Source track not found")
                continue

        frame = item.frame
        mix_track._set_latest_frame(source_track, frame)


async def mix_coro(mix_track: "MediaStreamMixTrack"):
    started_at = time.monotonic()

    while True:
        this_iter_start_time = time.monotonic()

        latest_frames = (
            await mix_track._get_latest_frames()
        )  # Wait for new frames arrive
        try:
            output_frame = mix_track._mixer_callback(latest_frames)

            if output_frame.pts is None and output_frame.time_base is None:
                timestamp = time.monotonic() - started_at
                if isinstance(output_frame, av.VideoFrame):
                    output_frame.pts = int(timestamp * VIDEO_CLOCK_RATE)
                    output_frame.time_base = VIDEO_TIME_BASE
                elif isinstance(output_frame, av.AudioFrame):
                    output_frame.pts = int(timestamp * AUDIO_SAMPLE_RATE)
                    output_frame.time_base = AUDIO_TIME_BASE

        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            for tb in traceback.format_exception(exc_type, exc_value, exc_traceback):
                for tbline in tb.rstrip().splitlines():
                    LOGGER.error(tbline.rstrip())
        mix_track._queue.put_nowait(output_frame)

        wait = this_iter_start_time + mix_track.mixer_output_interval - time.monotonic()
        await asyncio.sleep(wait)


class MediaStreamMixTrack(MediaStreamTrack, Generic[FrameT]):
    kind: str
    # _mixer_callback: MixerCallback  # Commented out this line due to a mypy problem: https://github.com/python/mypy/issues/2427  # noqa: E501
    _mixer_callback_lock: threading.Lock

    _loop: asyncio.AbstractEventLoop
    _input_proxies_lock: threading.Lock
    _input_proxies: "OrderedDict[MediaStreamTrack, RelayStreamTrack]"
    _input_tasks: "weakref.WeakKeyDictionary[RelayStreamTrack, asyncio.Task]"
    _input_queue: asyncio.Queue
    _queue: "asyncio.Queue[Optional[Frame]]"
    _latest_frames_map: (
        "weakref.WeakKeyDictionary[RelayStreamTrack, Union[Frame, Packet, None]]"
    )
    _latest_frames_updated_event: asyncio.Event

    _output_started: bool

    _gather_frames_task: Union[asyncio.Task, None]
    _mix_task: Union[asyncio.Task, None]

    mixer_output_interval: float

    def __init__(
        self,
        kind: str,
        mixer_callback: MixerCallback[FrameT],
        mixer_output_interval: float = 1 / 30,
    ) -> None:
        self.kind = kind
        self._mixer_callback: MixerCallback[FrameT] = mixer_callback
        self._mixer_callback_lock = threading.Lock()

        self.mixer_output_interval = mixer_output_interval

        loop = get_global_event_loop()

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
            self._mix_task = None

            self._output_started = False

    def _update_mixer_callback(self, mixer_callback: MixerCallback[FrameT]) -> None:
        with self._mixer_callback_lock:
            self._mixer_callback = mixer_callback

    def _start(self):
        if self._output_started:
            return

        self._gather_frames_task = self._loop.create_task(
            gather_frames_coro(mix_track=self)
        )
        self._mix_task = self._loop.create_task(mix_coro(mix_track=self))

        self._output_started = True

    def stop(self):
        super().stop()

        if self._gather_frames_task:
            self._gather_frames_task.cancel()
            self._gather_frames_task = None
        if self._mix_task:
            self._mix_task.cancel()
            self._mix_task = None

    def add_input_track(self, input_track: MediaStreamTrack) -> None:
        LOGGER.debug("Add a track %s to %s", input_track, self)

        with self._input_proxies_lock:
            if input_track in self._input_proxies:
                return

            relay = get_global_relay()
            with loop_context(self._loop):
                input_proxy = cast(RelayStreamTrack, relay.subscribe(input_track))

            self._input_proxies[input_track] = input_proxy

        LOGGER.debug(
            "A proxy %s subscribing %s is added to %s", input_proxy, input_track, self
        )

        task = self._loop.create_task(
            input_track_coro(input_track=input_proxy, mix_track=self)
        )
        self._input_tasks[input_proxy] = task

        input_proxy.on("ended", functools.partial(self.remove_input_proxy, input_proxy))

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
        self, input_proxy: RelayStreamTrack, frame: Union[Frame, Packet, None]
    ):
        # TODO: Lock here to make these 2 lines atomic
        self._latest_frames_map[input_proxy] = frame
        self._latest_frames_updated_event.set()

    async def _get_latest_frames(self) -> List[Union[Frame, Packet]]:
        # TODO: Lock here to make these 2 lines atomic
        await self._latest_frames_updated_event.wait()
        self._latest_frames_updated_event.clear()

        with self._input_proxies_lock:
            latest_frames = [
                self._latest_frames_map.get(proxy)
                for proxy in self._input_proxies.values()
            ]
        return [f for f in latest_frames if f is not None]

    async def recv(self):
        if self.readyState != "live":
            raise MediaStreamError

        self._start()

        frame = await self._queue.get()
        if frame is None:
            self.stop()
            raise MediaStreamError
        return frame
