import fractions

import av
import numpy as np
import pytest
import streamlit as st

import streamlit_webrtc.factory as factory
from streamlit_webrtc.factory import (
    create_audio_sink_track,
    create_audio_source_track,
    create_pcm_audio_source_track,
    create_video_sink_track,
    create_video_source_track,
)


class FakeSessionShutdownObserver:
    def __init__(self, callback):
        self.callback = callback
        self.stopped = False

    def stop(self):
        self.stopped = True


@pytest.fixture(autouse=True)
def clear_session_state(monkeypatch):
    monkeypatch.setattr(factory, "SessionShutdownObserver", FakeSessionShutdownObserver)
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    yield
    for key in list(st.session_state.keys()):
        del st.session_state[key]


def _video_callback(pts: int, time_base: fractions.Fraction) -> av.VideoFrame:
    buffer = np.zeros((4, 4, 3), dtype=np.uint8)
    return av.VideoFrame.from_ndarray(buffer, format="bgr24")


def _audio_callback(pts: int, time_base: fractions.Fraction) -> av.AudioFrame:
    samples = np.zeros((1, 960), dtype=np.int16)
    frame = av.AudioFrame.from_ndarray(samples, format="s16", layout="mono")
    frame.sample_rate = 48000
    return frame


def _sink_callback(frame) -> None:
    pass


def test_video_source_track_default_cache_behavior_is_unchanged():
    track1 = create_video_source_track(_video_callback, key="video")
    track2 = create_video_source_track(_video_callback, key="video")

    assert track2 is track1


def test_video_source_track_cache_generation_creates_fresh_track():
    track1 = create_video_source_track(
        _video_callback,
        key="video",
        cache_generation=1,
    )
    track2 = create_video_source_track(
        _video_callback,
        key="video",
        cache_generation=1,
    )
    track3 = create_video_source_track(
        _video_callback,
        key="video",
        cache_generation=2,
    )

    assert track2 is track1
    assert track3 is not track1
    assert track1.readyState == "ended"
    assert track3.readyState == "live"


def test_audio_source_track_cache_generation_creates_fresh_track():
    track1 = create_audio_source_track(
        _audio_callback,
        key="audio",
        cache_generation="first",
    )
    track2 = create_audio_source_track(
        _audio_callback,
        key="audio",
        cache_generation="first",
    )
    track3 = create_audio_source_track(
        _audio_callback,
        key="audio",
        cache_generation="second",
    )

    assert track2 is track1
    assert track3 is not track1
    assert track1.readyState == "ended"
    assert track3.readyState == "live"


def test_pcm_audio_source_cache_generation_creates_fresh_source():
    source1 = create_pcm_audio_source_track(
        key="pcm",
        sample_rate=48000,
        cache_generation=1,
    )
    source2 = create_pcm_audio_source_track(
        key="pcm",
        sample_rate=48000,
        cache_generation=1,
    )
    source3 = create_pcm_audio_source_track(
        key="pcm",
        sample_rate=48000,
        cache_generation=2,
    )

    assert source2 is source1
    assert source3 is not source1
    assert source1.track.readyState == "ended"
    assert source3.track.readyState == "live"


def test_sink_track_cache_generation_creates_fresh_tracks():
    video1 = create_video_sink_track(
        _sink_callback,
        key="video-sink",
        cache_generation=1,
    )
    video2 = create_video_sink_track(
        _sink_callback,
        key="video-sink",
        cache_generation=1,
    )
    video3 = create_video_sink_track(
        _sink_callback,
        key="video-sink",
        cache_generation=2,
    )

    audio1 = create_audio_sink_track(
        _sink_callback,
        key="audio-sink",
        cache_generation=1,
    )
    audio2 = create_audio_sink_track(
        _sink_callback,
        key="audio-sink",
        cache_generation=1,
    )
    audio3 = create_audio_sink_track(
        _sink_callback,
        key="audio-sink",
        cache_generation=2,
    )

    assert video2 is video1
    assert video3 is not video1
    assert audio2 is audio1
    assert audio3 is not audio1
