"""Run with a locally installed companion wheel to exercise the native transport."""

import asyncio
from fractions import Fraction

import av
import numpy as np
import pytest
from aiortc import MediaStreamTrack, RTCConfiguration, RTCPeerConnection

from streamlit_webrtc.native_webrtc import NativeAudioWorker

pytest.importorskip("streamlit_webrtc_native")


class ToneTrack(MediaStreamTrack):
    kind = "audio"

    def __init__(self):
        super().__init__()
        self.pts = 0
        self.start = None

    async def recv(self):
        loop = asyncio.get_running_loop()
        if self.start is None:
            self.start = loop.time()
        await asyncio.sleep(max(0, self.start + self.pts / 48000 - loop.time()))
        samples = np.arange(self.pts, self.pts + 960)
        data = (np.sin(samples * 2 * np.pi * 440 / 48000) * 10000).astype(np.int16)
        frame = av.AudioFrame.from_ndarray(
            data.reshape(1, -1), format="s16", layout="mono"
        )
        frame.sample_rate = 48000
        frame.pts, frame.time_base = self.pts, Fraction(1, 48000)
        self.pts += frame.samples
        return frame


@pytest.mark.asyncio
async def test_native_worker_transforms_audio_and_closes_after_remote_disconnect():
    loop = asyncio.get_running_loop()
    ended = asyncio.Event()
    input_peaks = []

    def transform(frame):
        input_peaks.append(np.max(np.abs(frame.to_ndarray())))
        samples = np.arange(frame.pts, frame.pts + frame.samples)
        data = (np.sin(samples * 2 * np.pi * 880 / 48000) * 10000).astype(np.int16)
        output = av.AudioFrame.from_ndarray(
            data.reshape(1, -1), format="s16", layout="mono"
        )
        output.sample_rate = 48000
        return output

    worker = NativeAudioWorker(
        rtc_configuration=RTCConfiguration(iceServers=[]),
        audio_frame_callback=transform,
        on_audio_ended=lambda: loop.call_soon_threadsafe(ended.set),
        async_processing=True,
        loop=loop,
    )
    client = RTCPeerConnection(RTCConfiguration(iceServers=[]))
    client.addTrack(ToneTrack())
    received = loop.create_future()

    @client.on("track")
    def on_track(track):
        received.set_result(track)

    try:
        await client.setLocalDescription(await client.createOffer())
        answer = await asyncio.to_thread(
            worker.process_offer, client.localDescription.sdp, "offer"
        )
        assert answer.sdp.count("m=audio") == 1
        assert "m=video" not in answer.sdp
        await client.setRemoteDescription(answer)
        track = await received
        frames = [await asyncio.wait_for(track.recv(), 5) for _ in range(30)]
        data = np.concatenate([frame.to_ndarray()[0] for frame in frames[-10:]])
        # aiortc decodes stereo Opus into packed, interleaved samples.
        channels = len(frames[-1].layout.channels)
        if not frames[-1].format.is_planar:
            data = data[::channels]
        spectrum = np.abs(np.fft.rfft(data.astype(float)))
        peak_hz = np.fft.rfftfreq(len(data), 1 / 48000)[np.argmax(spectrum)]
        assert peak_hz == pytest.approx(880, abs=10)
        assert max(input_peaks) > 1000
        await client.close()
        await asyncio.wait_for(ended.wait(), 12)
        assert worker._transport_closed
    finally:
        await asyncio.to_thread(worker.stop)
        await client.close()
        if worker._run_task is not None:
            await asyncio.wait_for(worker._run_task, 3)
