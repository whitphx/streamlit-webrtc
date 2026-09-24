from __future__ import annotations

import asyncio
from fractions import Fraction

import av
import numpy as np

from ._native import AudioPeer as _AudioPeer


class AudioPeer:
    """Experimental single-track, full-duplex audio peer."""

    def __init__(self, ice_servers: list[tuple[list[str], str, str]] | None = None):
        self._native = _AudioPeer(ice_servers or [])
        self._writer = asyncio.Lock()
        self._generation = 0
        self._pts = 0
        self._resampler = av.AudioResampler(format="s16", layout="mono", rate=48000)

    async def answer(self, sdp: str) -> str:
        return await self._native.answer(sdp)

    async def add_ice_candidate(self, mid: str, index: int, candidate: str) -> None:
        await self._native.add_ice_candidate(mid, index, candidate)

    async def recv(self) -> av.AudioFrame:
        pcm = await self._native.recv()
        samples = np.frombuffer(pcm, dtype="<i2").astype(np.int16, copy=False)
        frame = av.AudioFrame.from_ndarray(
            samples.reshape(1, -1), format="s16", layout="mono"
        )
        frame.sample_rate = 48000
        frame.time_base = Fraction(1, 48000)
        frame.pts = self._pts
        self._pts += frame.samples
        return frame

    async def send(self, frame: av.AudioFrame) -> None:
        generation = self._generation
        async with self._writer:
            if generation != self._generation:
                raise RuntimeError("output interrupted")
            # Producers may restart their timestamps for each utterance. Pacing is
            # owned by the native source; resampling must not depend on that clock.
            copy = av.AudioFrame.from_ndarray(
                frame.to_ndarray(), format=frame.format.name, layout=frame.layout.name
            )
            copy.sample_rate = frame.sample_rate
            for converted in self._resampler.resample(copy):
                pcm = converted.to_ndarray().astype("<i2", copy=False).tobytes()
                for start in range(0, len(pcm), 4800):
                    if generation != self._generation:
                        raise RuntimeError("output interrupted")
                    await self._native.send(pcm[start : start + 4800])

    async def clear_output(self) -> None:
        self._generation += 1
        await self._native.clear_output()
        async with self._writer:
            self._resampler = av.AudioResampler(format="s16", layout="mono", rate=48000)

    async def stats(self) -> dict[str, float]:
        return await self._native.stats()

    async def close(self) -> None:
        self._generation += 1
        await self._native.close()

    # Keep this annotation available on Python 3.10 without typing_extensions.
    async def __aenter__(self) -> AudioPeer:  # noqa: PYI034
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()
