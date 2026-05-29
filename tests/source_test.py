import asyncio
import fractions
import logging
import time

import av
import numpy as np
import pytest

from streamlit_webrtc.source import AudioSourceTrack, VideoSourceTrack


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


@pytest.mark.parametrize("sample_rate", [0, -1])
def test_audio_source_track_rejects_non_positive_sample_rate(sample_rate: int) -> None:
    with pytest.raises(ValueError, match="sample_rate"):
        AudioSourceTrack(callback=_make_callback(48000, 960), sample_rate=sample_rate)


def _video_callback(pts: int, time_base: fractions.Fraction) -> av.VideoFrame:
    buffer = np.zeros((4, 4, 3), dtype=np.uint8)
    return av.VideoFrame.from_ndarray(buffer, format="bgr24")


def test_video_source_track_fires_on_ended_on_stop() -> None:
    """Regression test for
    https://github.com/whitphx/streamlit-webrtc/issues/1800:
    source tracks need a deterministic notification when the session ends.
    """
    track = VideoSourceTrack(callback=_video_callback, fps=30)

    calls: list[int] = []
    track._on_ended_callback = lambda: calls.append(1)

    track.stop()

    assert calls == [1]


def test_audio_source_track_fires_on_ended_on_stop() -> None:
    track = AudioSourceTrack(callback=_make_callback(48000, 960), sample_rate=48000)

    calls: list[int] = []
    track._on_ended_callback = lambda: calls.append(1)

    track.stop()

    assert calls == [1]


def test_video_source_track_on_ended_exception_is_swallowed() -> None:
    """A misbehaving on_ended must not propagate into aiortc's event loop."""
    track = VideoSourceTrack(callback=_video_callback, fps=30)

    def boom() -> None:
        raise RuntimeError("boom")

    track._on_ended_callback = boom

    track.stop()


def _make_audio_callback_with_optional_delay(
    sample_rate: int, samples_per_frame: int, delay_on_call: dict[int, float]
):
    """Audio callback that sleeps `delay_on_call[n]` on the n-th invocation (1-based)."""
    call_count = [0]

    def callback(pts: int, time_base: fractions.Fraction) -> av.AudioFrame:
        call_count[0] += 1
        delay = delay_on_call.get(call_count[0], 0.0)
        if delay > 0:
            time.sleep(delay)
        samples = np.zeros((1, samples_per_frame), dtype=np.int16)
        frame = av.AudioFrame.from_ndarray(samples, format="s16", layout="mono")
        frame.sample_rate = sample_rate
        return frame

    return callback


@pytest.mark.parametrize("slow_call_index", [1, 2])
def test_audio_source_track_warns_when_callback_is_slow(
    caplog, slow_call_index: int
) -> None:
    ptime = 0.020
    sample_rate = 8000
    samples_per_frame = int(sample_rate * ptime)

    callback = _make_audio_callback_with_optional_delay(
        sample_rate=sample_rate,
        samples_per_frame=samples_per_frame,
        delay_on_call={slow_call_index: ptime * 2},
    )
    track = AudioSourceTrack(callback=callback, sample_rate=sample_rate, ptime=ptime)

    async def run():
        await track.recv()
        await track.recv()

    with caplog.at_level(logging.WARNING, logger="streamlit_webrtc.source"):
        asyncio.run(run())

    slow_warnings = [r for r in caplog.records if "too slow" in r.getMessage()]
    assert len(slow_warnings) == 1, [r.getMessage() for r in slow_warnings]


@pytest.mark.parametrize("slow_call_index", [1, 2])
def test_audio_source_track_does_not_warn_for_cumulative_drift(
    caplog, slow_call_index: int
) -> None:
    """Regression: one slow callback must not spam warnings on subsequent calls.

    The pre-fix implementation compared a cumulative wall-clock target
    (``_started_at + N * ptime``) against ``time.monotonic()``; once the
    wait went negative for any reason it stayed negative forever, so
    every fast callback after a single slow one produced a "too slow"
    warning. Per-frame timing isolates the diagnostic to the callback's
    own runtime.
    """
    ptime = 0.020
    sample_rate = 8000
    samples_per_frame = int(sample_rate * ptime)

    callback = _make_audio_callback_with_optional_delay(
        sample_rate=sample_rate,
        samples_per_frame=samples_per_frame,
        delay_on_call={slow_call_index: ptime * 2},
    )
    track = AudioSourceTrack(callback=callback, sample_rate=sample_rate, ptime=ptime)

    async def run():
        for _ in range(5):
            await track.recv()

    with caplog.at_level(logging.WARNING, logger="streamlit_webrtc.source"):
        asyncio.run(run())

    slow_warnings = [r for r in caplog.records if "too slow" in r.getMessage()]
    assert len(slow_warnings) == 1, [r.getMessage() for r in slow_warnings]


def _make_video_callback_with_optional_delay(delay_on_call: dict[int, float]):
    call_count = [0]

    def callback(pts: int, time_base: fractions.Fraction) -> av.VideoFrame:
        call_count[0] += 1
        delay = delay_on_call.get(call_count[0], 0.0)
        if delay > 0:
            time.sleep(delay)
        buffer = np.zeros((4, 4, 3), dtype=np.uint8)
        return av.VideoFrame.from_ndarray(buffer, format="bgr24")

    return callback


@pytest.mark.parametrize("slow_call_index", [1, 2])
def test_video_source_track_warns_when_callback_is_slow(
    caplog, slow_call_index: int
) -> None:
    fps = 30
    frame_budget = 1.0 / fps

    callback = _make_video_callback_with_optional_delay(
        delay_on_call={slow_call_index: frame_budget * 2}
    )
    track = VideoSourceTrack(callback=callback, fps=fps)

    async def run():
        await track.recv()
        await track.recv()

    with caplog.at_level(logging.WARNING, logger="streamlit_webrtc.source"):
        asyncio.run(run())

    slow_warnings = [r for r in caplog.records if "too slow" in r.getMessage()]
    assert len(slow_warnings) == 1, [r.getMessage() for r in slow_warnings]


@pytest.mark.parametrize("slow_call_index", [1, 2])
def test_video_source_track_does_not_warn_for_cumulative_drift(
    caplog, slow_call_index: int
) -> None:
    fps = 30
    frame_budget = 1.0 / fps

    callback = _make_video_callback_with_optional_delay(
        delay_on_call={slow_call_index: frame_budget * 2}
    )
    track = VideoSourceTrack(callback=callback, fps=fps)

    async def run():
        for _ in range(5):
            await track.recv()

    with caplog.at_level(logging.WARNING, logger="streamlit_webrtc.source"):
        asyncio.run(run())

    slow_warnings = [r for r in caplog.records if "too slow" in r.getMessage()]
    assert len(slow_warnings) == 1, [r.getMessage() for r in slow_warnings]
