"""Streamed-PCM source track with a thread-safe push/clear interface."""

from __future__ import annotations

import fractions
import threading
from typing import Union

import av
import numpy as np
import numpy.typing as npt

from .source import AUDIO_PTIME, AudioSourceTrack


class PcmAudioSource:
    """Streamed-PCM source track with a thread-safe push/clear interface.

    Backs an :class:`AudioSourceTrack` with an internal :class:`av.AudioFifo`
    so an arbitrary producer (background thread, async session, WebSocket
    handler) can push s16-mono PCM samples at irregular cadence while the
    aiortc media loop pulls fixed-size frames at ``ptime``. Underruns are
    padded with silence to keep the track on schedule.

    The track is only s16 mono for now — the common shape for realtime
    audio APIs (TTS, voice LLMs, ASR echo). Stereo / float layouts would
    be a future extension.
    """

    track: AudioSourceTrack

    def __init__(self, *, sample_rate: int, ptime: float = AUDIO_PTIME) -> None:
        if sample_rate <= 0:
            raise ValueError(
                f"sample_rate must be a positive integer, got {sample_rate}"
            )
        if ptime <= 0:
            raise ValueError(f"ptime must be a positive number, got {ptime}")
        samples_per_frame = int(sample_rate * ptime)
        if samples_per_frame <= 0:
            raise ValueError(
                f"ptime ({ptime}) is too small for sample_rate ({sample_rate}); "
                "int(sample_rate * ptime) must be >= 1"
            )
        self._sample_rate = sample_rate
        self._ptime = ptime
        self._samples_per_frame = samples_per_frame
        # PyAV's AudioFifo isn't documented thread-safe and we have a
        # producer (caller's thread) and consumer (aiortc media loop)
        # touching it concurrently.
        self._fifo = av.AudioFifo()
        self._lock = threading.Lock()
        self.track = AudioSourceTrack(
            callback=self._source_callback,
            sample_rate=sample_rate,
            ptime=ptime,
        )

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def ptime(self) -> float:
        return self._ptime

    def push(
        self, pcm: Union[bytes, bytearray, memoryview, npt.NDArray[np.int16]]
    ) -> None:
        """Append PCM samples to the playback queue.

        ``bytes`` / ``bytearray`` / ``memoryview`` inputs are interpreted as
        little-endian s16 mono samples (the universal wire shape). A numpy
        array must be 1-D and have dtype ``int16``.
        """
        if isinstance(pcm, (bytes, bytearray, memoryview)):
            samples = np.frombuffer(pcm, dtype=np.int16)
        else:
            samples = np.asarray(pcm)
            if samples.dtype != np.int16:
                raise ValueError(
                    f"pcm ndarray must have dtype int16, got {samples.dtype}"
                )
            if samples.ndim != 1:
                raise ValueError(
                    f"pcm ndarray must be 1-D mono, got shape {samples.shape}"
                )
        if samples.size == 0:
            return
        frame = av.AudioFrame.from_ndarray(
            samples.reshape(1, -1), format="s16", layout="mono"
        )
        frame.sample_rate = self._sample_rate
        with self._lock:
            self._fifo.write(frame)

    def clear(self) -> None:
        """Drop all buffered samples (e.g. on barge-in)."""
        with self._lock:
            # AudioFifo has no in-place reset; the cheapest equivalent
            # is a fresh instance.
            self._fifo = av.AudioFifo()

    def _source_callback(
        self, pts: int, time_base: fractions.Fraction
    ) -> av.AudioFrame:
        n = self._samples_per_frame
        with self._lock:
            frame = self._fifo.read(n, partial=True)
        out = np.zeros((1, n), dtype=np.int16)
        if frame is not None:
            available = frame.to_ndarray()
            out[:, : available.shape[1]] = available
        result = av.AudioFrame.from_ndarray(out, format="s16", layout="mono")
        result.sample_rate = self._sample_rate
        return result
