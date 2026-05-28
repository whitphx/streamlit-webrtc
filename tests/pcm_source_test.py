import asyncio
import threading
from typing import cast

import av
import numpy as np
import pytest

from streamlit_webrtc.pcm_source import PcmAudioSource


def _consume(source: PcmAudioSource, n_frames: int) -> np.ndarray:
    """Pull ``n_frames`` audio frames from the track and return their samples."""

    async def run() -> list[av.AudioFrame]:
        return [cast(av.AudioFrame, await source.track.recv()) for _ in range(n_frames)]

    frames = asyncio.run(run())
    return np.concatenate([f.to_ndarray().reshape(-1) for f in frames])


def test_push_bytes_plays_back_in_order() -> None:
    src = PcmAudioSource(sample_rate=8000, ptime=0.020)
    samples_per_frame = int(8000 * 0.020)  # 160

    pcm = np.arange(1, samples_per_frame * 2 + 1, dtype=np.int16).tobytes()
    src.push(pcm)

    out = _consume(src, 2)
    expected = np.arange(1, samples_per_frame * 2 + 1, dtype=np.int16)
    assert np.array_equal(out, expected)


def test_push_ndarray_plays_back_in_order() -> None:
    src = PcmAudioSource(sample_rate=8000, ptime=0.020)
    samples_per_frame = int(8000 * 0.020)

    arr = np.arange(1, samples_per_frame * 3 + 1, dtype=np.int16)
    src.push(arr)

    out = _consume(src, 3)
    assert np.array_equal(out, arr)


def test_underrun_is_silence_padded() -> None:
    src = PcmAudioSource(sample_rate=8000, ptime=0.020)
    samples_per_frame = int(8000 * 0.020)

    # Push half a frame; consume two full frames.
    partial = np.arange(1, samples_per_frame // 2 + 1, dtype=np.int16)
    src.push(partial)

    out = _consume(src, 2)
    assert out.shape == (samples_per_frame * 2,)
    # First half matches what we pushed; the rest is silence.
    assert np.array_equal(out[: partial.size], partial)
    assert (out[partial.size :] == 0).all()


def test_clear_drops_buffered_samples() -> None:
    src = PcmAudioSource(sample_rate=8000, ptime=0.020)
    samples_per_frame = int(8000 * 0.020)

    src.push(np.arange(1, samples_per_frame * 4 + 1, dtype=np.int16))
    src.clear()

    out = _consume(src, 1)
    assert (out == 0).all()


def test_frame_metadata_matches_configured_rate() -> None:
    src = PcmAudioSource(sample_rate=16000, ptime=0.020)

    src.push(np.zeros(320, dtype=np.int16))

    async def run():
        return await src.track.recv()

    frame = asyncio.run(run())
    assert frame.sample_rate == 16000
    assert frame.format.name == "s16"
    assert frame.layout.name == "mono"
    assert frame.samples == int(16000 * 0.020)


def test_push_rejects_non_int16_ndarray() -> None:
    src = PcmAudioSource(sample_rate=8000)
    with pytest.raises(ValueError, match="int16"):
        src.push(np.zeros(160, dtype=np.float32))


def test_push_rejects_multidim_ndarray() -> None:
    src = PcmAudioSource(sample_rate=8000)
    with pytest.raises(ValueError, match="1-D"):
        src.push(np.zeros((2, 160), dtype=np.int16))


def test_push_empty_is_noop() -> None:
    src = PcmAudioSource(sample_rate=8000, ptime=0.020)
    src.push(b"")
    src.push(np.zeros(0, dtype=np.int16))

    out = _consume(src, 1)
    assert (out == 0).all()


@pytest.mark.parametrize("sample_rate", [0, -1])
def test_rejects_non_positive_sample_rate(sample_rate: int) -> None:
    with pytest.raises(ValueError, match="sample_rate"):
        PcmAudioSource(sample_rate=sample_rate)


@pytest.mark.parametrize("ptime", [0.0, -0.020])
def test_rejects_non_positive_ptime(ptime: float) -> None:
    with pytest.raises(ValueError, match="ptime"):
        PcmAudioSource(sample_rate=8000, ptime=ptime)


def test_rejects_ptime_smaller_than_one_sample() -> None:
    # 8000 * 0.0001 == 0.8, floors to 0 → degenerate frame size.
    with pytest.raises(ValueError, match="too small"):
        PcmAudioSource(sample_rate=8000, ptime=0.0001)


def test_push_is_thread_safe() -> None:
    """Concurrent producers must not corrupt the FIFO (total sample count
    matches the sum of pushed lengths)."""
    src = PcmAudioSource(sample_rate=48000, ptime=0.020)

    per_thread = 5000
    n_threads = 8

    def producer() -> None:
        src.push(np.ones(per_thread, dtype=np.int16))

    threads = [threading.Thread(target=producer) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Consume enough frames to drain everything we pushed.
    samples_per_frame = int(48000 * 0.020)  # 960
    total_pushed = per_thread * n_threads
    frames_needed = (total_pushed + samples_per_frame - 1) // samples_per_frame
    out = _consume(src, frames_needed)

    # Every pushed sample is a 1, and we drained at least that many; the
    # leading `total_pushed` samples must all be 1.
    assert (out[:total_pushed] == 1).all()
