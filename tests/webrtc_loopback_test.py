"""Layer-3 integration tests: aiortc loopback against a real `WebRtcWorker`.

These run both ends of the WebRTC connection in-process by injecting the
test's running event loop into `WebRtcWorker(loop=…, relay=…)`.

Each test owns its setup and teardown explicitly inside the coroutine body.
Doing teardown from a (sync) pytest fixture left aiortc tasks racing the
loop's shutdown and produced nondeterministic `RTCIceTransport is closed`
failures.
"""

import asyncio
import fractions
from typing import Any, Dict, List

import av
import numpy as np
import pytest
from aiortc import RTCPeerConnection
from aiortc.contrib.media import MediaRelay

from streamlit_webrtc.source import VideoSourceTrack
from streamlit_webrtc.webrtc import WebRtcMode, WebRtcWorker

_WORKER_DEFAULTS: Dict[str, Any] = dict(
    rtc_configuration=None,
    source_video_track=None,
    source_audio_track=None,
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
