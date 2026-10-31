import asyncio
import fractions
from typing import List, Optional

import av
import numpy as np
import pytest
from aiortc import RTCPeerConnection
from aiortc.contrib.media import MediaRelay

from streamlit_webrtc.source import AudioSourceTrack
from streamlit_webrtc.webrtc import WebRtcMode, WebRtcWorker

from .webrtc_loopback_test import _WORKER_DEFAULTS, _drain_until, _wire_ice

CLICK_FRAME = 60
CLICK_OFFSET = 123


@pytest.mark.asyncio
@pytest.mark.parametrize("sample_rate", [16000, 48000])
async def test_rtp_timestamp_matches_where_the_receiver_decodes_the_sample(
    sample_rate: int,
) -> None:
    loop = asyncio.get_running_loop()
    samples_per_frame = sample_rate // 50
    click_pts = CLICK_FRAME * samples_per_frame + CLICK_OFFSET
    worker: Optional[WebRtcWorker] = None
    predicted: List[Optional[int]] = []

    def source(pts: int, time_base: fractions.Fraction) -> av.AudioFrame:
        samples = np.zeros((1, samples_per_frame), dtype=np.int16)
        if pts <= click_pts < pts + samples_per_frame:
            samples[0, click_pts - pts :] = 20000
            assert worker is not None
            predicted.append(worker.rtp_timestamp("audio", click_pts, time_base))
        frame = av.AudioFrame.from_ndarray(samples, format="s16", layout="mono")
        frame.sample_rate = sample_rate
        return frame

    client = RTCPeerConnection()
    receiver = client.addTransceiver("audio", direction="recvonly").receiver
    first_rtp: List[int] = []
    handle_rtp_packet = receiver._handle_rtp_packet

    async def record_first_rtp(packet, arrival_time_ms):
        if not first_rtp:
            first_rtp.append(packet.timestamp)
        await handle_rtp_packet(packet, arrival_time_ms)

    # aiortc's receiver numbers decoded frames from the first packet's RTP
    # timestamp, which only the packet itself still carries.
    receiver._handle_rtp_packet = record_first_rtp  # type: ignore[method-assign]
    onset: List[int] = []

    @client.on("track")  # type: ignore[arg-type]
    def _on_track(track):  # pragma: no cover - aiortc-driven
        async def _drain():
            while not onset:
                try:
                    frame = await track.recv()
                except Exception:
                    return
                level = np.abs(frame.to_ndarray().reshape(-1, 2)[:, 0])
                loud = np.flatnonzero(level > 5000)
                if loud.size:
                    onset.append((first_rtp[0] + frame.pts + int(loud[0])) & 0xFFFFFFFF)

        asyncio.ensure_future(_drain())

    worker = WebRtcWorker(
        loop=loop,
        relay=MediaRelay(),
        mode=WebRtcMode.SENDRECV,
        **{
            **_WORKER_DEFAULTS,
            "source_audio_track": AudioSourceTrack(source, sample_rate=sample_rate),
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
        assert await _drain_until(lambda: bool(onset), loop.time() + 15)
        assert predicted and predicted[0] is not None
        error = ((onset[0] - predicted[0] + 2**31) % 2**32) - 2**31
        # The resampler's and the codec's filters smear a step over a few
        # samples, so the onset is only exact to within a millisecond.
        assert abs(error) <= 48, f"onset {error} samples off the prediction"
    finally:
        await asyncio.to_thread(worker.stop, 1.0)
        await client.close()
        await asyncio.sleep(0.2)
