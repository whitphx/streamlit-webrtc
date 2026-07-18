"""Tests for the decoder-thread shutdown guard.

aiortc's ``RTCRtpReceiver`` runs a *non-daemon* decoder thread that exits
only when a ``None`` sentinel reaches its queue, normally sent by
``pc.close()``. If the event loop dies before the close runs, that thread
blocks interpreter exit (``threading._shutdown`` joins non-daemon threads).
These tests cover the force-stop helper, the ``WebRtcWorker.stop()``
fallback, and the worker registry behind the interpreter-exit hook.
"""

import asyncio
import threading

import pytest
from aiortc import RTCPeerConnection
from aiortc.contrib.media import MediaRelay
from aiortc.mediastreams import VideoStreamTrack

import streamlit_webrtc.webrtc as webrtc_module
from streamlit_webrtc.webrtc import (
    WebRtcMode,
    WebRtcWorker,
    _force_stop_decoder_threads,
    _live_workers,
    _stop_leaked_decoder_threads_at_interpreter_exit,
)

from .webrtc_loopback_test import _WORKER_DEFAULTS, _wire_ice


def _decoder_threads():
    return [t for t in threading.enumerate() if t.name.endswith("-decoder")]


async def _wait_for(predicate, timeout: float) -> bool:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if predicate():
            return True
        await asyncio.sleep(0.1)
    return predicate()


@pytest.mark.asyncio
async def test_force_stop_decoder_threads_releases_nondaemon_decoder_threads():
    pc1 = RTCPeerConnection()
    pc2 = RTCPeerConnection()
    pc1.addTrack(VideoStreamTrack())

    @pc2.on("track")  # type: ignore[arg-type]
    def on_track(track):  # pragma: no cover - aiortc-driven
        async def consume():
            while True:
                try:
                    await track.recv()
                except Exception:
                    return

        asyncio.ensure_future(consume())

    await pc1.setLocalDescription(await pc1.createOffer())
    await pc2.setRemoteDescription(pc1.localDescription)
    await pc2.setLocalDescription(await pc2.createAnswer())
    await pc1.setRemoteDescription(pc2.localDescription)

    try:
        assert await _wait_for(lambda: len(_decoder_threads()) > 0, 15)
        decoder_threads = _decoder_threads()
        # The premise of the guard: these threads are non-daemon, so leaking
        # them would block interpreter exit.
        assert all(not t.daemon for t in decoder_threads)

        _force_stop_decoder_threads(pc2)

        assert await _wait_for(
            lambda: not any(t.is_alive() for t in decoder_threads), 5
        )
    finally:
        await pc1.close()
        await pc2.close()
        # Give aiortc's background cleanup tasks a moment so leftover tasks
        # don't get hard-cancelled when pytest-asyncio closes the loop.
        await asyncio.sleep(0.2)


def _make_bare_worker() -> WebRtcWorker:
    worker = object.__new__(WebRtcWorker)
    worker._process_offer_thread = None
    worker._session_shutdown_observer = None
    worker._video_processor = None
    worker._audio_processor = None
    worker._video_receiver = None
    worker._audio_receiver = None
    worker.sink_video_track = None
    worker.sink_audio_track = None
    worker._player = None
    worker._relayed_source_audio_track = None
    worker.source_audio_track = None
    worker._relayed_source_video_track = None
    worker.source_video_track = None
    return worker


class _FakeReceiver:
    def __init__(self, force_stopped: list):
        self._force_stopped = force_stopped

    def _RTCRtpReceiver__stop_decoder(self):
        self._force_stopped.append(self)


class _FakeTransceiver:
    def __init__(self, force_stopped: list):
        self.receiver = _FakeReceiver(force_stopped)


class _FakePeerConnection:
    def __init__(self, connection_state: str, force_stopped: list):
        self.connectionState = connection_state
        self._transceivers = [
            _FakeTransceiver(force_stopped),
            _FakeTransceiver(force_stopped),
        ]

    async def close(self) -> None:
        pass

    def getTransceivers(self):
        return self._transceivers


def test_worker_stop_force_stops_decoders_when_loop_is_closed() -> None:
    worker = _make_bare_worker()

    force_stopped: list = []

    class FakeClosedLoop:
        def is_running(self) -> bool:
            return False

        def run_until_complete(self, coro):
            coro.close()
            raise RuntimeError("Event loop is closed")

    worker._loop = FakeClosedLoop()  # type: ignore[assignment]
    worker.pc = _FakePeerConnection("connected", force_stopped)  # type: ignore[assignment]

    worker.stop(timeout=0.1)

    assert len(force_stopped) == 2


def test_worker_stop_force_stops_decoders_when_connection_already_closed() -> None:
    """`connectionState` turns "closed" at the *start* of
    `RTCPeerConnection.close()`, so a close interrupted mid-flight (event-loop
    teardown, a timed-out or cancelled close task) leaves an already-"closed"
    connection that still owns live decoder threads. `stop()` must force-stop
    them even though it skips the close attempt."""
    worker = _make_bare_worker()

    force_stopped: list = []

    class ExplodingLoop:
        # `stop()` must not touch the loop at all on this path.
        def is_running(self) -> bool:
            raise AssertionError("the loop must not be used")

    worker._loop = ExplodingLoop()  # type: ignore[assignment]
    worker.pc = _FakePeerConnection("closed", force_stopped)  # type: ignore[assignment]

    worker.stop(timeout=0.1)

    assert len(force_stopped) == 2


@pytest.mark.asyncio
async def test_worker_stop_releases_decoders_after_teardown_style_closure(monkeypatch):
    """End-to-end: reproduce the state event-loop teardown leaves behind —
    DTLS pump tasks cancelled (which skips `_handle_disconnect`, so decoder
    threads stay alive) and `pc.close()` never able to run — then check
    `worker.stop()` still releases the decoder threads."""
    loop = asyncio.get_running_loop()
    client = RTCPeerConnection()
    client.addTrack(VideoStreamTrack())
    worker: WebRtcWorker = WebRtcWorker(
        loop=loop,
        relay=MediaRelay(),
        mode=WebRtcMode.SENDONLY,
        **_WORKER_DEFAULTS,
    )
    _wire_ice(client, worker)
    await client.setLocalDescription(await client.createOffer())
    answer = await asyncio.to_thread(
        worker.process_offer,
        client.localDescription.sdp,
        client.localDescription.type,
        10,
    )
    await client.setRemoteDescription(answer)

    try:
        assert await _wait_for(lambda: len(_decoder_threads()) > 0, 15)
        decoder_threads = _decoder_threads()

        # In real event-loop teardown the `pc.close()` task that aiortc
        # self-schedules on reaching the "closed" state never gets to run
        # (the loop stops first). Neuter `close` so this test reproduces
        # that state instead of letting the live test loop run it — without
        # this, the decoders get released with or without the fix and the
        # test discriminates nothing.
        async def _close_never_runs():
            pass

        monkeypatch.setattr(worker.pc, "close", _close_never_runs)

        for transceiver in worker.pc.getTransceivers():
            transport = transceiver.receiver.transport
            if transport._task is not None:
                transport._task.cancel()
                transport._task = None
        assert await _wait_for(
            lambda: all(
                t.receiver.transport.state == "closed"
                for t in worker.pc.getTransceivers()
            ),
            5,
        )
        assert any(t.is_alive() for t in decoder_threads)

        await asyncio.to_thread(worker.stop, 1.0)

        assert await _wait_for(
            lambda: not any(t.is_alive() for t in decoder_threads), 5
        )
    finally:
        await asyncio.to_thread(worker.stop, 1.0)
        await client.close()
        await asyncio.sleep(0.2)


def test_live_worker_registry_and_exit_hook(monkeypatch) -> None:
    loop = asyncio.new_event_loop()
    try:
        worker: WebRtcWorker = WebRtcWorker(
            loop=loop,
            relay=MediaRelay(),
            mode=WebRtcMode.SENDRECV,
            **_WORKER_DEFAULTS,
        )
        assert worker in _live_workers

        forced: list = []
        monkeypatch.setattr(webrtc_module, "_force_stop_decoder_threads", forced.append)
        _stop_leaked_decoder_threads_at_interpreter_exit()
        assert worker.pc in forced

        worker.stop(timeout=1.0)
        assert worker not in _live_workers
    finally:
        loop.close()
