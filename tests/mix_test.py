"""Layer-2 tests for `mix.MediaStreamMixTrack`.

Inject the test's running loop + a fresh `MediaRelay` into the mix track
(introduced when the class was decoupled from the Streamlit runtime), so
the input-pumping and mixer coroutines run on the same loop the test
itself owns. No real WebRTC connection involved — input tracks are
simple `VideoSourceTrack`s yielding constant frames.
"""

import asyncio
import fractions
import time
from typing import List

import av
import numpy as np
import pytest
from aiortc.contrib.media import MediaRelay

from streamlit_webrtc.mix import MediaStreamMixTrack
from streamlit_webrtc.source import VideoSourceTrack


def _video_source_callback(pts: int, time_base: fractions.Fraction) -> av.VideoFrame:
    arr = np.zeros((16, 16, 3), dtype=np.uint8)
    return av.VideoFrame.from_ndarray(arr, format="bgr24")


def _output_frame() -> av.VideoFrame:
    arr = np.full((16, 16, 3), 7, dtype=np.uint8)
    return av.VideoFrame.from_ndarray(arr, format="bgr24")


async def _teardown(
    mix_track: MediaStreamMixTrack, inputs: List[VideoSourceTrack]
) -> None:
    mix_track.stop()
    for t in inputs:
        t.stop()
    # Give the gather / mix / input-pumping tasks a chance to unwind before
    # pytest-asyncio closes the loop.
    await asyncio.sleep(0.1)


@pytest.mark.asyncio
async def test_mixer_callback_receives_a_single_input() -> None:
    loop = asyncio.get_running_loop()
    received: List[List[av.VideoFrame]] = []

    def mixer_cb(frames: List[av.VideoFrame]) -> av.VideoFrame:
        received.append(list(frames))
        return _output_frame()

    mix_track: MediaStreamMixTrack = MediaStreamMixTrack(
        kind="video",
        mixer_callback=mixer_cb,
        mixer_output_interval=1 / 60,
        loop=loop,
        relay=MediaRelay(),
    )
    source = VideoSourceTrack(_video_source_callback, fps=30)
    mix_track.add_input_track(source)

    try:
        outputs = [await mix_track.recv() for _ in range(3)]
        assert len(outputs) == 3
        # Each invocation saw exactly one input frame — there's only one
        # input track registered.
        assert len(received) >= 3
        assert all(len(frames) == 1 for frames in received[:3])
    finally:
        await _teardown(mix_track, [source])


@pytest.mark.asyncio
async def test_mixer_callback_receives_multiple_inputs() -> None:
    loop = asyncio.get_running_loop()
    received: List[List[av.VideoFrame]] = []

    def mixer_cb(frames: List[av.VideoFrame]) -> av.VideoFrame:
        received.append(list(frames))
        return _output_frame()

    mix_track: MediaStreamMixTrack = MediaStreamMixTrack(
        kind="video",
        mixer_callback=mixer_cb,
        mixer_output_interval=1 / 60,
        loop=loop,
        relay=MediaRelay(),
    )
    source_a = VideoSourceTrack(_video_source_callback, fps=30)
    source_b = VideoSourceTrack(_video_source_callback, fps=30)
    mix_track.add_input_track(source_a)
    mix_track.add_input_track(source_b)

    try:
        # Drain several outputs to give both inputs time to register frames.
        for _ in range(8):
            await mix_track.recv()

        # The mix callback's input list is built from whatever sources have
        # delivered a frame so far — early iterations may only see one of
        # the two because the inputs warm up independently. At least one
        # call must include both inputs.
        assert any(len(frames) == 2 for frames in received)
    finally:
        await _teardown(mix_track, [source_a, source_b])


@pytest.mark.asyncio
async def test_mixer_output_cadence_tracks_configured_interval() -> None:
    """Successive `recv()` calls should be roughly spaced by `mixer_output_interval`."""
    loop = asyncio.get_running_loop()
    interval = 0.05  # 50ms

    def mixer_cb(frames: List[av.VideoFrame]) -> av.VideoFrame:
        return _output_frame()

    mix_track: MediaStreamMixTrack = MediaStreamMixTrack(
        kind="video",
        mixer_callback=mixer_cb,
        mixer_output_interval=interval,
        loop=loop,
        relay=MediaRelay(),
    )
    source = VideoSourceTrack(_video_source_callback, fps=60)
    mix_track.add_input_track(source)

    try:
        # Warm up — the first frame can land essentially immediately because
        # the mix loop doesn't wait for an interval before producing it.
        await mix_track.recv()

        start = time.monotonic()
        for _ in range(3):
            await mix_track.recv()
        elapsed = time.monotonic() - start

        # 3 more frames after the warm-up means ~3 intervals of work, give
        # generous bounds for scheduler jitter.
        assert interval * 2 < elapsed < interval * 8
    finally:
        await _teardown(mix_track, [source])
