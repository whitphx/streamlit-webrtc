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
    set_default_factory_reset_key,
)


class FakeSessionShutdownObserver:
    instances: list["FakeSessionShutdownObserver"] = []

    def __init__(self, callback):
        self.callback = callback
        self.stopped = False
        self.__class__.instances.append(self)

    def stop(self):
        self.stopped = True


@pytest.fixture(autouse=True)
def clear_session_state(monkeypatch):
    monkeypatch.setattr(factory, "SessionShutdownObserver", FakeSessionShutdownObserver)
    FakeSessionShutdownObserver.instances.clear()
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
    track3 = create_video_source_track(_video_callback, key="other-video")

    assert track2 is track1
    assert track3 is not track1


def test_audio_source_track_default_cache_behavior_is_unchanged():
    track1 = create_audio_source_track(_audio_callback, key="audio")
    track2 = create_audio_source_track(_audio_callback, key="audio")
    track3 = create_audio_source_track(_audio_callback, key="other-audio")

    assert track2 is track1
    assert track3 is not track1


def test_pcm_audio_source_default_cache_behavior_is_unchanged():
    source1 = create_pcm_audio_source_track(key="pcm", sample_rate=48000)
    source2 = create_pcm_audio_source_track(key="pcm", sample_rate=48000)
    source3 = create_pcm_audio_source_track(key="other-pcm", sample_rate=48000)

    assert source2 is source1
    assert source3 is not source1


def test_sink_track_default_cache_behavior_is_unchanged():
    video1 = create_video_sink_track(_sink_callback, key="video-sink")
    video2 = create_video_sink_track(_sink_callback, key="video-sink")
    video3 = create_video_sink_track(_sink_callback, key="other-video-sink")

    audio1 = create_audio_sink_track(_sink_callback, key="audio-sink")
    audio2 = create_audio_sink_track(_sink_callback, key="audio-sink")
    audio3 = create_audio_sink_track(_sink_callback, key="other-audio-sink")

    assert video2 is video1
    assert video3 is not video1
    assert audio2 is audio1
    assert audio3 is not audio1


def test_video_source_track_uses_default_reset_key():
    set_default_factory_reset_key(1)
    track1 = create_video_source_track(_video_callback, key="video")
    track2 = create_video_source_track(_video_callback, key="video")

    set_default_factory_reset_key(2)
    track3 = create_video_source_track(_video_callback, key="video")

    assert track2 is track1
    assert track3 is not track1
    assert track1.readyState == "ended"
    assert track3.readyState == "live"
    assert any(observer.stopped for observer in FakeSessionShutdownObserver.instances)


def test_clearing_default_reset_key_restores_key_only_cache_behavior():
    set_default_factory_reset_key(1)
    reset_track = create_video_source_track(_video_callback, key="video")

    set_default_factory_reset_key(None)
    track1 = create_video_source_track(_video_callback, key="video")
    track2 = create_video_source_track(_video_callback, key="video")

    set_default_factory_reset_key(2)
    track3 = create_video_source_track(_video_callback, key="video")

    assert track1 is not reset_track
    assert reset_track.readyState == "ended"
    assert track2 is track1
    assert track3 is not track1
    assert track1.readyState == "ended"
    assert any(observer.stopped for observer in FakeSessionShutdownObserver.instances)


def test_active_reset_metadata_does_not_collide_with_user_keys():
    collision_key = "__ACTIVE_CACHE_KEY__video"

    set_default_factory_reset_key(1)
    reset_track = create_video_source_track(_video_callback, key="video")

    set_default_factory_reset_key(None)
    collision_track1 = create_video_source_track(_video_callback, key=collision_key)
    collision_track2 = create_video_source_track(_video_callback, key=collision_key)

    assert collision_track2 is collision_track1
    assert collision_track1 is not reset_track

    key_only_track = create_video_source_track(_video_callback, key="video")

    assert key_only_track is not reset_track
    assert reset_track.readyState == "ended"


def test_reset_key_cache_entry_does_not_collide_with_user_keys():
    collision_key = "video__RESET_KEY__int:1"

    reset_track = create_video_source_track(
        _video_callback,
        key="video",
        reset_key=1,
    )
    key_only_track1 = create_video_source_track(_video_callback, key=collision_key)
    key_only_track2 = create_video_source_track(_video_callback, key=collision_key)

    assert key_only_track1 is not reset_track
    assert key_only_track2 is key_only_track1
    assert reset_track.readyState == "live"


def test_bool_reset_key_is_rejected():
    with pytest.raises(TypeError, match="reset_key"):
        set_default_factory_reset_key(True)

    with pytest.raises(TypeError, match="reset_key"):
        create_video_source_track(_video_callback, key="video", reset_key=True)


def test_video_source_track_reset_key_creates_fresh_track():
    track1 = create_video_source_track(
        _video_callback,
        key="video",
        reset_key=1,
    )
    track2 = create_video_source_track(
        _video_callback,
        key="video",
        reset_key=1,
    )
    track3 = create_video_source_track(
        _video_callback,
        key="video",
        reset_key=2,
    )

    assert track2 is track1
    assert track3 is not track1
    assert track1.readyState == "ended"
    assert track3.readyState == "live"
    assert any(observer.stopped for observer in FakeSessionShutdownObserver.instances)


def test_audio_source_track_reset_key_creates_fresh_track():
    track1 = create_audio_source_track(
        _audio_callback,
        key="audio",
        reset_key="first",
    )
    track2 = create_audio_source_track(
        _audio_callback,
        key="audio",
        reset_key="first",
    )
    track3 = create_audio_source_track(
        _audio_callback,
        key="audio",
        reset_key="second",
    )

    assert track2 is track1
    assert track3 is not track1
    assert track1.readyState == "ended"
    assert track3.readyState == "live"
    assert any(observer.stopped for observer in FakeSessionShutdownObserver.instances)


def test_pcm_audio_source_reset_key_creates_fresh_source():
    source1 = create_pcm_audio_source_track(
        key="pcm",
        sample_rate=48000,
        reset_key=1,
    )
    source2 = create_pcm_audio_source_track(
        key="pcm",
        sample_rate=48000,
        reset_key=1,
    )
    source3 = create_pcm_audio_source_track(
        key="pcm",
        sample_rate=48000,
        reset_key=2,
    )

    assert source2 is source1
    assert source3 is not source1
    assert source1.track.readyState == "ended"
    assert source3.track.readyState == "live"
    assert any(observer.stopped for observer in FakeSessionShutdownObserver.instances)


def test_sink_track_reset_key_creates_fresh_tracks():
    video1 = create_video_sink_track(
        _sink_callback,
        key="video-sink",
        reset_key=1,
    )
    video2 = create_video_sink_track(
        _sink_callback,
        key="video-sink",
        reset_key=1,
    )
    video3 = create_video_sink_track(
        _sink_callback,
        key="video-sink",
        reset_key=2,
    )

    audio1 = create_audio_sink_track(
        _sink_callback,
        key="audio-sink",
        reset_key=1,
    )
    audio2 = create_audio_sink_track(
        _sink_callback,
        key="audio-sink",
        reset_key=1,
    )
    audio3 = create_audio_sink_track(
        _sink_callback,
        key="audio-sink",
        reset_key=2,
    )

    assert video2 is video1
    assert video3 is not video1
    assert audio2 is audio1
    assert audio3 is not audio1
    assert any(observer.stopped for observer in FakeSessionShutdownObserver.instances)
