import asyncio
import fractions

import av
import numpy as np
import pytest

from streamlit_webrtc.source import AudioSourceTrack


def _make_callback(sample_rate: int, samples_per_frame: int):
    def callback(pts: int, time_base: fractions.Fraction) -> av.AudioFrame:
        samples = np.zeros((1, samples_per_frame), dtype=np.int16)
        frame = av.AudioFrame.from_ndarray(samples, format="s16", layout="mono")
        frame.sample_rate = sample_rate
        return frame

    return callback


@pytest.mark.parametrize("sample_rate", [8000, 16000, 44100, 48000])
def test_audio_source_track_time_base_matches_sample_rate(sample_rate: int) -> None:
    """frame.pts * frame.time_base must advance by exactly ptime seconds per call.

    Regression test for
    https://github.com/whitphx/streamlit-webrtc/issues/2405:
    AudioSourceTrack used a hard-coded 1/48000 time_base, causing the
    receiver to play audio at the wrong speed when sample_rate != 48000.
    """
    ptime = 0.020
    samples_per_frame = int(sample_rate * ptime)

    track = AudioSourceTrack(
        callback=_make_callback(sample_rate, samples_per_frame),
        sample_rate=sample_rate,
        ptime=ptime,
    )

    async def run():
        frames = []
        for _ in range(3):
            frames.append(await track.recv())
        return frames

    frames = asyncio.run(run())

    assert all(f.time_base == fractions.Fraction(1, sample_rate) for f in frames)

    # frame.pts * frame.time_base should advance by exactly ptime per call.
    timestamps = [float(f.pts * f.time_base) for f in frames]
    assert timestamps[0] == pytest.approx(0.0)
    assert timestamps[1] == pytest.approx(ptime)
    assert timestamps[2] == pytest.approx(2 * ptime)
