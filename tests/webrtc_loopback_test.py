"""Layer-3 integration tests: aiortc loopback against a real `WebRtcWorker`.

These run both ends of the WebRTC connection in-process by injecting the
test's running event loop into `WebRtcWorker(loop=…, relay=…)`.

Each test owns its setup and teardown explicitly inside the coroutine body.
Doing teardown from a (sync) pytest fixture left aiortc tasks racing the
loop's shutdown and produced nondeterministic `RTCIceTransport is closed`
failures.
"""

import asyncio
import concurrent.futures
import fractions
from typing import Any, Dict, List, Set

import av
import numpy as np
import pytest
from aiortc import RTCPeerConnection
from aiortc.contrib.media import MediaRelay

from streamlit_webrtc.sink import AudioSinkTrack, VideoSinkTrack
from streamlit_webrtc.source import AudioSourceTrack, VideoSourceTrack
from streamlit_webrtc.webrtc import WebRtcMode, WebRtcWorker

_WORKER_DEFAULTS: Dict[str, Any] = dict(
    rtc_configuration=None,
    source_video_track=None,
    source_audio_track=None,
    sink_video_track=None,
    sink_audio_track=None,
    player_factory=None,
    in_recorder_factory=None,
    out_recorder_factory=None,
    video_frame_callback=None,
    audio_frame_callback=None,
    queued_video_frames_callback=None,
    queued_audio_frames_callback=None,
    on_video_ended=None,
    on_audio_ended=None,
    video_processor_factory=None,
    audio_processor_factory=None,
    async_processing=True,
    video_receiver_size=4,
    audio_receiver_size=4,
    sendback_video=True,
    sendback_audio=True,
)


def _source_callback(pts: int, time_base: fractions.Fraction) -> av.VideoFrame:
    arr = np.zeros((32, 32, 3), dtype=np.uint8)
    return av.VideoFrame.from_ndarray(arr, format="bgr24")


def test_worker_stop_waits_for_peer_connection_close(monkeypatch) -> None:
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

    closed = {"submitted": False, "waited": False}

    class CloseFuture(concurrent.futures.Future[None]):
        def result(self, timeout=None) -> None:
            closed["waited"] = True
            return super().result(timeout=timeout)

    close_future = CloseFuture()
    close_future.set_result(None)

    class FakeLoop:
        def is_running(self) -> bool:
            return True

    class FakePeerConnection:
        connectionState = "connected"

        async def close(self) -> None:
            pass

        def getTransceivers(self):
            return []

    def run_coroutine_threadsafe(coro, loop):
        coro.close()
        assert isinstance(loop, FakeLoop)
        closed["submitted"] = True
        return close_future

    monkeypatch.setattr(asyncio, "run_coroutine_threadsafe", run_coroutine_threadsafe)
    worker._loop = FakeLoop()  # type: ignore[assignment]
    worker.pc = FakePeerConnection()  # type: ignore[assignment]

    worker.stop(timeout=1.0)

    assert closed == {"submitted": True, "waited": True}


def _wire_ice(client: RTCPeerConnection, worker: WebRtcWorker) -> None:
    """Trickle ICE candidates in both directions.

    aiortc's `setLocalDescription` waits for ICE gathering, so host
    candidates are embedded in the initial SDP. But aiortc still emits
    `icecandidate` events afterward; without these wirings, in-process
    loopback occasionally stalls before the connection completes.
    """

    @client.on("icecandidate")  # type: ignore[arg-type]
    async def _to_worker(c):  # pragma: no cover - aiortc-driven
        if c is not None:
            worker.add_ice_candidate(c)

    @worker.pc.on("icecandidate")  # type: ignore[arg-type]
    async def _to_client(c):  # pragma: no cover - aiortc-driven
        if c is not None:
            await client.addIceCandidate(c)


async def _drain_until(predicate, deadline: float) -> bool:
    loop = asyncio.get_running_loop()
    while loop.time() < deadline:
        if predicate():
            return True
        await asyncio.sleep(0.1)
    return predicate()


async def _setup_loopback(
    *, mode: WebRtcMode, **worker_overrides: Any
) -> "tuple[RTCPeerConnection, WebRtcWorker]":
    """Build a client / worker pair and complete the SDP handshake.

    The caller is responsible for tearing both sides down with
    `_teardown_loopback` while the loop is still running.
    """
    loop = asyncio.get_running_loop()
    client = RTCPeerConnection()
    client.addTrack(VideoSourceTrack(_source_callback, fps=15))

    worker: WebRtcWorker = WebRtcWorker(
        loop=loop,
        relay=MediaRelay(),
        mode=mode,
        **{**_WORKER_DEFAULTS, **worker_overrides},
    )
    _wire_ice(client, worker)
    await client.setLocalDescription(await client.createOffer())
    assert client.localDescription is not None
    answer = await asyncio.to_thread(
        worker.process_offer,
        client.localDescription.sdp,
        client.localDescription.type,
        10,
    )
    await client.setRemoteDescription(answer)
    return client, worker


async def _teardown_loopback(client: RTCPeerConnection, worker: WebRtcWorker) -> None:
    await asyncio.to_thread(worker.stop, 1.0)
    await client.close()
    # Give aiortc's background cleanup tasks a moment so leftover tasks don't
    # get hard-cancelled when pytest-asyncio closes the loop.
    await asyncio.sleep(0.2)


@pytest.mark.asyncio
async def test_sendonly_video_frame_callback_observes_frames() -> None:
    loop = asyncio.get_running_loop()
    received: List[av.VideoFrame] = []

    def cb(frame: av.VideoFrame) -> av.VideoFrame:
        received.append(frame)
        return frame

    client, worker = await _setup_loopback(
        mode=WebRtcMode.SENDONLY, video_frame_callback=cb
    )
    try:
        # Generous deadline — aiortc connection establishment is the long pole.
        assert await _drain_until(lambda: len(received) >= 1, loop.time() + 15)
    finally:
        await _teardown_loopback(client, worker)


def _audio_source_callback(pts: int, time_base: fractions.Fraction) -> av.AudioFrame:
    samples = np.zeros((1, 960), dtype=np.int16)
    frame = av.AudioFrame.from_ndarray(samples, format="s16", layout="mono")
    frame.sample_rate = 48000
    return frame


@pytest.mark.asyncio
async def test_sendrecv_audio_only_input_with_source_video_track() -> None:
    """SENDRECV with audio-only peer input still delivers `source_video_track`.

    Regression test for the case where the developer wants to receive audio
    from the browser AND send back a server-generated video stream. The
    worker used to attach output tracks only inside `on_track`, which fires
    once per incoming peer kind, so the configured `source_video_track` was
    silently dropped when the peer didn't send video.
    """
    loop = asyncio.get_running_loop()
    client = RTCPeerConnection()
    client.addTrack(AudioSourceTrack(_audio_source_callback, sample_rate=48000))
    # Mirror the frontend behavior: explicitly request a video stream from
    # the server even though the client isn't sending one.
    client.addTransceiver("video", direction="recvonly")

    received_kinds: Set[str] = set()

    @client.on("track")  # type: ignore[arg-type]
    def _on_track(track):  # pragma: no cover - aiortc-driven
        received_kinds.add(track.kind)

    server_source = VideoSourceTrack(_source_callback, fps=15)
    worker: WebRtcWorker = WebRtcWorker(
        loop=loop,
        relay=MediaRelay(),
        mode=WebRtcMode.SENDRECV,
        **{**_WORKER_DEFAULTS, "source_video_track": server_source},
    )
    _wire_ice(client, worker)
    await client.setLocalDescription(await client.createOffer())
    assert client.localDescription is not None
    answer = await asyncio.to_thread(
        worker.process_offer,
        client.localDescription.sdp,
        client.localDescription.type,
        10,
    )
    await client.setRemoteDescription(answer)

    try:
        assert await _drain_until(lambda: "video" in received_kinds, loop.time() + 15)
        assert worker.output_video_track is not None
    finally:
        await _teardown_loopback(client, worker)


@pytest.mark.asyncio
async def test_update_video_callbacks_hot_swap() -> None:
    """A live callback hot-swap reaches subsequent frames.

    `CallbackAttachableProcessor.update_callbacks` is unit-tested in
    `models_test.py`; this test proves the wiring all the way from
    `WebRtcWorker.update_video_callbacks` through the async track wrapper
    to the callback that ends up consuming frames.
    """
    loop = asyncio.get_running_loop()
    counter = {"first": 0, "second": 0}

    def first(frame: av.VideoFrame) -> av.VideoFrame:
        counter["first"] += 1
        return frame

    def second(frame: av.VideoFrame) -> av.VideoFrame:
        counter["second"] += 1
        return frame

    client, worker = await _setup_loopback(
        mode=WebRtcMode.SENDONLY, video_frame_callback=first
    )
    try:
        assert await _drain_until(lambda: counter["first"] >= 1, loop.time() + 15)
        worker.update_video_callbacks(
            frame_callback=second, queued_frames_callback=None, on_ended=None
        )
        # Frames must now reach `second`; `first` may continue briefly while
        # in-flight queued frames drain, so don't assert `first` stops.
        assert await _drain_until(lambda: counter["second"] >= 1, loop.time() + 15)
    finally:
        await _teardown_loopback(client, worker)


@pytest.mark.asyncio
async def test_sendonly_video_sink_track_receives_frames() -> None:
    """SENDONLY with an explicit ``sink_video_track`` — no auto-receiver."""
    loop = asyncio.get_running_loop()
    received: List[av.VideoFrame] = []
    sink = VideoSinkTrack(callback=received.append)

    client, worker = await _setup_loopback(
        mode=WebRtcMode.SENDONLY, sink_video_track=sink
    )
    try:
        assert await _drain_until(lambda: len(received) >= 1, loop.time() + 15)
        # Auto-receiver must be suppressed when a sink is explicitly provided.
        assert worker.video_receiver is None
    finally:
        await _teardown_loopback(client, worker)


@pytest.mark.asyncio
async def test_sendrecv_audio_sink_with_independent_video_source() -> None:
    """Audio-in via sink, video-out via source at independent FPS.

    Mirrors ``pages/16_audio_in_video_out.py`` but using a sink for the
    input side, which is the no-drop replacement for the implicit return-
    value coupling of ``audio_frame_callback``.
    """
    loop = asyncio.get_running_loop()
    audio_frames: List[av.AudioFrame] = []
    sink = AudioSinkTrack(callback=audio_frames.append)

    client = RTCPeerConnection()
    client.addTrack(AudioSourceTrack(_audio_source_callback, sample_rate=48000))
    client.addTransceiver("video", direction="recvonly")

    received_video = {"count": 0}

    @client.on("track")  # type: ignore[arg-type]
    def _on_track(track):  # pragma: no cover - aiortc-driven
        if track.kind != "video":
            return

        async def _drain():
            while True:
                try:
                    await track.recv()
                except Exception:
                    return
                received_video["count"] += 1

        asyncio.ensure_future(_drain())

    server_source = VideoSourceTrack(_source_callback, fps=15)
    worker: WebRtcWorker = WebRtcWorker(
        loop=loop,
        relay=MediaRelay(),
        mode=WebRtcMode.SENDRECV,
        **{
            **_WORKER_DEFAULTS,
            "source_video_track": server_source,
            "sink_audio_track": sink,
        },
    )
    _wire_ice(client, worker)
    await client.setLocalDescription(await client.createOffer())
    assert client.localDescription is not None
    answer = await asyncio.to_thread(
        worker.process_offer,
        client.localDescription.sdp,
        client.localDescription.type,
        10,
    )
    await client.setRemoteDescription(answer)

    try:
        assert await _drain_until(lambda: len(audio_frames) >= 1, loop.time() + 15), (
            "audio sink callback was never invoked"
        )
        assert await _drain_until(
            lambda: received_video["count"] >= 1, loop.time() + 15
        ), "server-generated video was never received"
        # No audio output should have been wired (sink + no source for kind).
        assert worker.output_audio_track is None
    finally:
        await _teardown_loopback(client, worker)


@pytest.mark.asyncio
async def test_sink_track_swap_across_sessions() -> None:
    """A cached sink can be reused for a new peer track after the prior
    session ends — readyState falls back to ``new`` so ``addTrack`` works
    again on the next worker."""
    loop = asyncio.get_running_loop()
    received_a: List[av.VideoFrame] = []
    sink = VideoSinkTrack(callback=received_a.append)

    client_a, worker_a = await _setup_loopback(
        mode=WebRtcMode.SENDONLY, sink_video_track=sink
    )
    try:
        assert await _drain_until(lambda: len(received_a) >= 1, loop.time() + 15)
    finally:
        await _teardown_loopback(client_a, worker_a)

    assert sink.readyState in ("new", "ended"), sink.readyState

    received_b: List[av.VideoFrame] = []
    sink._callback = received_b.append  # mirror what create_video_sink_track does

    client_b, worker_b = await _setup_loopback(
        mode=WebRtcMode.SENDONLY, sink_video_track=sink
    )
    try:
        assert await _drain_until(lambda: len(received_b) >= 1, loop.time() + 15)
    finally:
        await _teardown_loopback(client_b, worker_b)
