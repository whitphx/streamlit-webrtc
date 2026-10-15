import asyncio
import fractions
import threading
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any
from unittest.mock import Mock

import av
import numpy as np
import pytest
import pytest_asyncio
from aiortc import RTCConfiguration, RTCIceServer

from streamlit_webrtc import native_webrtc
from streamlit_webrtc.native_webrtc import NativeAudioWorker
from streamlit_webrtc.webrtc import SignallingTimeoutError


class FakePeer:
    def __init__(self, *, ice_servers: list) -> None:
        self.ice_servers = ice_servers
        self.frames: asyncio.Queue[av.AudioFrame] = asyncio.Queue()
        self.sent: asyncio.Queue[av.AudioFrame] = asyncio.Queue()
        self.candidates: asyncio.Queue[tuple[str, int, str]] = asyncio.Queue()
        self.closed = asyncio.Event()
        self.close_calls = 0
        self.clear_calls = 0
        self.answer_started = asyncio.Event()
        self.answer_gate: asyncio.Event | None = None
        self.answer_error: Exception | None = None

    async def answer(self, sdp: str) -> str:
        self.answer_started.set()
        if self.answer_gate is not None:
            await self.answer_gate.wait()
        if self.answer_error is not None:
            raise self.answer_error
        return "native answer"

    async def recv(self) -> av.AudioFrame:
        return await self.frames.get()

    async def send(self, frame: av.AudioFrame) -> None:
        self.sent.put_nowait(frame)

    async def add_ice_candidate(self, mid: str, index: int, value: str) -> None:
        self.candidates.put_nowait((mid, index, value))

    async def clear_output(self) -> None:
        self.clear_calls += 1

    async def close(self) -> None:
        self.close_calls += 1
        self.closed.set()


@dataclass
class WorkerCase:
    worker: NativeAudioWorker
    peer: FakePeer
    observer: Mock
    ended: threading.Event
    ended_calls: list[None]


@pytest_asyncio.fixture
async def make_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[Callable[..., WorkerCase]]:
    cases: list[WorkerCase] = []

    def make(**kwargs: Any) -> WorkerCase:
        peer = FakePeer(ice_servers=[])
        observer = Mock()

        def peer_factory(*, ice_servers: list) -> FakePeer:
            peer.ice_servers = ice_servers
            return peer

        monkeypatch.setattr(native_webrtc, "load_native_peer", lambda: peer_factory)
        monkeypatch.setattr(
            native_webrtc, "SessionShutdownObserver", lambda callback: observer
        )
        ended = threading.Event()
        ended_calls: list[None] = []

        def on_ended() -> None:
            ended_calls.append(None)
            ended.set()

        options: dict[str, Any] = dict(
            rtc_configuration=None,
            audio_frame_callback=None,
            on_audio_ended=on_ended,
            async_processing=True,
            loop=asyncio.get_running_loop(),
        )
        options.update(kwargs)
        worker = NativeAudioWorker(**options)
        case = WorkerCase(worker, peer, observer, ended, ended_calls)
        cases.append(case)
        return case

    yield make

    for case in cases:
        await asyncio.to_thread(case.worker.stop)
        if case.worker._run_task is not None:
            await asyncio.wait_for(case.worker._run_task, 2)


def audio_frame(value: int, *, pts: int = 960) -> av.AudioFrame:
    frame = av.AudioFrame.from_ndarray(
        np.full((1, 480), value, dtype=np.int16), format="s16", layout="mono"
    )
    frame.sample_rate = 48000
    frame.pts = pts
    frame.time_base = fractions.Fraction(1, 48000)
    return frame


async def start(case: WorkerCase) -> None:
    answer = await asyncio.to_thread(case.worker.process_offer, "offer", "offer")
    assert answer is case.worker.local_description
    assert answer.sdp == "native answer"
    assert answer.type == "answer"


async def wait_thread_event(event: threading.Event) -> None:
    assert await asyncio.to_thread(event.wait, 2)


@pytest.mark.asyncio
@pytest.mark.parametrize("async_processing", [False, True])
async def test_callback_transforms_samples_and_restores_timing(
    make_worker, async_processing: bool
) -> None:
    def callback(frame: av.AudioFrame) -> av.AudioFrame:
        result = audio_frame(int(frame.to_ndarray()[0, 0]) * 3, pts=123)
        result.time_base = fractions.Fraction(1, 16000)
        return result

    case = make_worker(audio_frame_callback=callback, async_processing=async_processing)
    await start(case)
    original = audio_frame(7)
    case.peer.frames.put_nowait(original)
    result = await asyncio.wait_for(case.peer.sent.get(), 2)
    assert np.all(result.to_ndarray() == 21)
    assert result.pts == original.pts
    assert result.time_base == original.time_base


@pytest.mark.asyncio
async def test_callback_can_be_added_and_removed_during_stream(make_worker) -> None:
    case = make_worker()
    await start(case)
    case.peer.frames.put_nowait(audio_frame(1))
    assert np.all((await asyncio.wait_for(case.peer.sent.get(), 2)).to_ndarray() == 1)

    case.worker.update_audio_callbacks(lambda frame: audio_frame(9), None, None)
    case.peer.frames.put_nowait(audio_frame(2))
    assert np.all((await asyncio.wait_for(case.peer.sent.get(), 2)).to_ndarray() == 9)

    case.worker.update_audio_callbacks(None, None, None)
    case.peer.frames.put_nowait(audio_frame(3))
    assert np.all((await asyncio.wait_for(case.peer.sent.get(), 2)).to_ndarray() == 3)


@pytest.mark.asyncio
async def test_clear_discards_pending_callback_and_resumes_next_frame(
    make_worker,
) -> None:
    entered, release = threading.Event(), threading.Event()

    def callback(frame: av.AudioFrame) -> av.AudioFrame:
        if frame.pts == 480:
            entered.set()
            assert release.wait(3)
        return frame

    case = make_worker(audio_frame_callback=callback)
    await start(case)
    try:
        case.peer.frames.put_nowait(audio_frame(1, pts=480))
        await wait_thread_event(entered)
        await asyncio.wait_for(asyncio.to_thread(case.worker.clear_audio_output), 1)
        assert case.peer.clear_calls == 1
        case.peer.frames.put_nowait(audio_frame(2, pts=960))
        release.set()
        result = await asyncio.wait_for(case.peer.sent.get(), 2)
        assert result.pts == 960
        assert np.all(result.to_ndarray() == 2)
        assert case.peer.sent.empty()
    finally:
        release.set()


@pytest.mark.asyncio
async def test_stop_before_first_frame_closes_and_calls_ended_once(make_worker) -> None:
    case = make_worker()
    await start(case)
    await asyncio.to_thread(case.worker.stop)
    await wait_thread_event(case.ended)
    await asyncio.to_thread(case.worker.stop)
    assert case.peer.close_calls == 1
    assert case.ended_calls == [None]
    case.observer.stop.assert_called()


@pytest.mark.asyncio
async def test_stop_during_callback_closes_before_waiting_for_callback(
    make_worker,
) -> None:
    entered, release = threading.Event(), threading.Event()

    def callback(frame: av.AudioFrame) -> av.AudioFrame:
        entered.set()
        assert release.wait(3)
        return frame

    case = make_worker(audio_frame_callback=callback)
    await start(case)
    try:
        case.peer.frames.put_nowait(audio_frame(1))
        await wait_thread_event(entered)
        await asyncio.wait_for(asyncio.to_thread(case.worker.stop), 1)
        assert case.peer.closed.is_set()
        assert not case.ended.is_set()
        release.set()
        await wait_thread_event(case.ended)
        await asyncio.to_thread(case.worker.stop)
        assert case.ended_calls == [None]
        assert case.peer.sent.empty()
        assert case.peer.close_calls == 1
    finally:
        release.set()


@pytest.mark.asyncio
async def test_stop_from_media_loop_does_not_block(make_worker) -> None:
    case = make_worker()
    await start(case)
    case.worker.stop()
    await asyncio.wait_for(case.peer.closed.wait(), 1)
    await wait_thread_event(case.ended)
    assert case.ended_calls == [None]


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_result", [False, True])
async def test_callback_failure_closes_transport(
    make_worker, invalid_result: bool
) -> None:
    def callback(frame: av.AudioFrame) -> Any:
        if invalid_result:
            return None
        raise ValueError("processor failed")

    case = make_worker(audio_frame_callback=callback)
    await start(case)
    case.peer.frames.put_nowait(audio_frame(1))
    await asyncio.wait_for(case.peer.closed.wait(), 2)
    await wait_thread_event(case.ended)
    assert case.peer.sent.empty()
    assert case.ended_calls == [None]


@pytest.mark.asyncio
async def test_negotiation_error_closes_transport(make_worker) -> None:
    case = make_worker()
    case.peer.answer_error = ValueError("bad offer")
    with pytest.raises(ValueError, match="bad offer"):
        await asyncio.to_thread(case.worker.process_offer, "offer", "offer")
    await asyncio.wait_for(case.peer.closed.wait(), 2)
    await wait_thread_event(case.ended)
    assert case.peer.close_calls == 1


@pytest.mark.asyncio
async def test_negotiation_timeout_cancels_answer_and_closes(make_worker) -> None:
    case = make_worker()
    case.peer.answer_gate = asyncio.Event()
    with pytest.raises(SignallingTimeoutError):
        await asyncio.to_thread(case.worker.process_offer, "offer", "offer", 0.05)
    assert case.peer.answer_started.is_set()
    await asyncio.wait_for(case.peer.closed.wait(), 2)
    await wait_thread_event(case.ended)
    assert case.worker.local_description is None
    assert case.peer.close_calls == 1


@pytest.mark.asyncio
async def test_candidates_wait_for_answer_and_deduplicate(make_worker) -> None:
    case = make_worker()
    case.peer.answer_gate = asyncio.Event()
    negotiation = asyncio.create_task(
        asyncio.to_thread(case.worker.process_offer, "offer", "offer")
    )
    await asyncio.wait_for(case.peer.answer_started.wait(), 1)
    candidate = {"sdpMid": "audio", "sdpMLineIndex": 0, "candidate": "candidate:1"}
    case.worker.set_ice_candidates_from_offerer({"one": candidate, "bad": None})
    case.worker.set_ice_candidates_from_offerer({"one": candidate})
    await asyncio.sleep(0)
    assert case.peer.candidates.empty()
    case.peer.answer_gate.set()
    await negotiation
    assert await asyncio.wait_for(case.peer.candidates.get(), 2) == (
        "audio",
        0,
        "candidate:1",
    )
    await asyncio.sleep(0)
    assert case.peer.candidates.empty()


@pytest.mark.asyncio
async def test_ice_configuration_reaches_companion(make_worker) -> None:
    case = make_worker(
        rtc_configuration=RTCConfiguration(
            iceServers=[
                RTCIceServer(urls="stun:example.org"),
                RTCIceServer(
                    urls=["turn:example.org", "turns:example.org"],
                    username="user",
                    credential="password",
                ),
            ]
        )
    )
    await start(case)
    assert case.peer.ice_servers == [
        (["stun:example.org"], "", ""),
        (["turn:example.org", "turns:example.org"], "user", "password"),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("async_processing", [False, True])
async def test_callback_can_stop_worker_without_losing_ended_notification(
    make_worker, async_processing: bool
) -> None:
    def callback(frame: av.AudioFrame) -> av.AudioFrame:
        case.worker.stop()
        return frame

    case = make_worker(audio_frame_callback=callback, async_processing=async_processing)
    await start(case)
    case.peer.frames.put_nowait(audio_frame(1))
    await asyncio.wait_for(case.peer.closed.wait(), 2)
    await wait_thread_event(case.ended)
    assert case.ended_calls == [None]
    assert case.peer.sent.empty()
