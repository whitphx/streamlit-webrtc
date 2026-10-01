import asyncio
from fractions import Fraction
from itertools import pairwise

import av
import numpy as np
import pytest
from aiortc import (
    MediaStreamTrack,
    RTCConfiguration,
    RTCPeerConnection,
    RTCSessionDescription,
)
from aiortc.mediastreams import MediaStreamError

from streamlit_webrtc_native import AudioPeer


def tone(samples=960, rate=48000, frequency=440):
    data = (np.sin(np.arange(samples) * 2 * np.pi * frequency / rate) * 10000).astype(
        np.int16
    )
    frame = av.AudioFrame.from_ndarray(data.reshape(1, -1), format="s16", layout="mono")
    frame.sample_rate = rate
    return frame


class ToneTrack(MediaStreamTrack):
    kind = "audio"

    def __init__(self):
        super().__init__()
        self.pts = 0
        self.start = None

    async def recv(self):
        if self.readyState != "live":
            raise MediaStreamError
        loop = asyncio.get_running_loop()
        if self.start is None:
            self.start = loop.time()
        await asyncio.sleep(max(0, self.start + self.pts / 48000 - loop.time()))
        frame = tone()
        frame.pts, frame.time_base = self.pts, Fraction(1, 48000)
        self.pts += frame.samples
        return frame


async def connect(native):
    client = RTCPeerConnection(RTCConfiguration(iceServers=[]))
    client.addTrack(ToneTrack())
    output = asyncio.get_running_loop().create_future()

    @client.on("track")
    def on_track(track):
        if not output.done():
            output.set_result(track)

    try:
        await client.setLocalDescription(await client.createOffer())
        sdp = await asyncio.wait_for(native.answer(client.localDescription.sdp), 10)
        await client.setRemoteDescription(RTCSessionDescription(sdp=sdp, type="answer"))
        return client, await output
    except BaseException:
        await client.close()
        raise


@pytest.mark.parametrize("rate", [24000, 48000])
async def test_full_duplex(rate):
    async with AudioPeer() as peer:
        client, output = await connect(peer)
        try:

            async def produce():
                for _ in range(50):
                    await peer.send(tone(rate // 50, rate))

            sender = asyncio.create_task(produce())
            received = []
            for _ in range(30):
                frame = await asyncio.wait_for(peer.recv(), 3)
                assert frame.sample_rate == 48000
                assert frame.layout.name == "mono"
                assert frame.format.name == "s16"
                received.append(frame)
            assert all(b.pts == a.pts + a.samples for a, b in pairwise(received))
            assert any(np.max(np.abs(f.to_ndarray())) > 1000 for f in received)
            browser_frames = [
                await asyncio.wait_for(output.recv(), 3) for _ in range(10)
            ]
            assert any(np.max(np.abs(f.to_ndarray())) > 1000 for f in browser_frames)
            await sender
            assert (await peer.stats())["packets_received"] > 0
        finally:
            await client.close()


async def test_interrupt_pending_writers_and_resume():
    async with AudioPeer() as peer:
        client, output = await connect(peer)
        try:
            pending = [asyncio.create_task(peer.send(tone(48000))) for _ in range(3)]
            await asyncio.sleep(0.05)
            await asyncio.wait_for(peer.clear_output(), 0.5)
            results = await asyncio.gather(*pending, return_exceptions=True)
            assert all(
                isinstance(r, RuntimeError) and "interrupted" in str(r) for r in results
            )
            await asyncio.wait_for(peer.send(tone()), 1)
            assert (await asyncio.wait_for(output.recv(), 3)).samples > 0
        finally:
            await client.close()


async def test_close_unblocks_receive_and_is_idempotent():
    peer = AudioPeer()
    receive = asyncio.create_task(peer.recv())
    await asyncio.sleep(0.01)
    await asyncio.wait_for(peer.close(), 1)
    with pytest.raises(RuntimeError, match="closed"):
        await receive
    await peer.close()
    with pytest.raises(RuntimeError, match="closed"):
        await peer.send(tone())


async def test_remote_close_ends_receive_and_allows_local_cleanup():
    peer = AudioPeer()
    client, _ = await connect(peer)
    try:
        for _ in range(30):
            await asyncio.wait_for(peer.recv(), 3)
        await client.close()

        async def receive_until_closed():
            while True:
                await peer.recv()

        with pytest.raises(RuntimeError, match="closed"):
            await asyncio.wait_for(receive_until_closed(), 10)
        with pytest.raises(RuntimeError, match="closed"):
            await peer.send(tone())
        await asyncio.wait_for(peer.close(), 3)
        await asyncio.wait_for(peer.close(), 3)
    finally:
        await client.close()
        await peer.close()


async def test_invalid_offer_and_close_during_negotiation():
    async with AudioPeer() as peer:
        with pytest.raises(RuntimeError):
            await peer.answer("not SDP")
    peer = AudioPeer()
    client = RTCPeerConnection(RTCConfiguration(iceServers=[]))
    client.addTrack(ToneTrack())
    try:
        offer = await client.createOffer()
        task = asyncio.create_task(peer.answer(offer.sdp))
        await peer.close()
        with pytest.raises(RuntimeError, match="closed"):
            await task
    finally:
        await client.close()


async def test_repeated_sessions_and_starvation():
    for _ in range(3):
        async with AudioPeer() as peer:
            client, output = await connect(peer)
            try:
                await asyncio.wait_for(peer.recv(), 3)
                await asyncio.sleep(0.3)
                frame = await asyncio.wait_for(peer.recv(), 1)
                assert frame.samples == 480
                await peer.send(tone())
                await asyncio.wait_for(output.recv(), 3)
            finally:
                await client.close()


async def test_slow_consumer_does_not_accumulate_old_audio():
    async with AudioPeer() as peer:
        client, _ = await connect(peer)
        try:
            await asyncio.wait_for(peer.recv(), 3)
            await asyncio.sleep(0.5)
            start = asyncio.get_running_loop().time()
            for _ in range(25):
                await asyncio.wait_for(peer.recv(), 1)
            assert asyncio.get_running_loop().time() - start >= 0.09
        finally:
            await client.close()


async def test_cancelled_send_keeps_native_writer_serialized():
    async with AudioPeer() as peer:
        client, _ = await connect(peer)
        try:
            sending = asyncio.create_task(peer.send(tone(48000)))
            await asyncio.sleep(0.01)
            sending.cancel()
            with pytest.raises(asyncio.CancelledError):
                await sending
            await asyncio.wait_for(peer.clear_output(), 0.5)
            await asyncio.wait_for(peer.send(tone()), 1)
        finally:
            await client.close()


async def test_close_acknowledges_pending_capture():
    peer = AudioPeer()
    client, _ = await connect(peer)
    try:
        sending = asyncio.create_task(peer.send(tone(48000)))
        await asyncio.sleep(0.01)
        await asyncio.wait_for(peer.close(), 0.5)
        with pytest.raises(RuntimeError, match="closed|interrupted"):
            await sending
    finally:
        await peer.close()
        await client.close()


async def test_rejects_video_offer():
    async with AudioPeer() as peer:
        client = RTCPeerConnection(RTCConfiguration(iceServers=[]))
        client.addTrack(ToneTrack())
        client.addTransceiver("video")
        try:
            offer = await client.createOffer()
            with pytest.raises(ValueError, match="one audio"):
                await peer.answer(offer.sdp)
        finally:
            await client.close()
