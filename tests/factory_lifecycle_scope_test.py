import fractions
import threading
from types import SimpleNamespace
from typing import Callable

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
from streamlit_webrtc.webrtc import _reset_factory_cache_on_webrtc_session_end


class FakeSessionShutdownObserver:
    instances: list["FakeSessionShutdownObserver"] = []

    def __init__(self, callback):
        self.callback = callback
        self.stopped = False
        self.__class__.instances.append(self)

    def stop(self):
        self.stopped = True


class ItemOnlySessionState:
    """SafeSessionState-like test double.

    Streamlit's production ScriptRunContext exposes SafeSessionState, which
    supports item access but not mapping helpers such as get() or pop().
    """

    def __init__(self):
        self._items = {}

    def __contains__(self, key):
        return key in self._items

    def __getitem__(self, key):
        return self._items[key]

    def __setitem__(self, key, value):
        self._items[key] = value

    def __delitem__(self, key):
        del self._items[key]


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


def _run_in_thread(callback: Callable[[], object]) -> None:
    errors: list[BaseException] = []

    def run():
        try:
            callback()
        except Exception as e:
            errors.append(e)

    thread = threading.Thread(target=run)
    thread.start()
    thread.join(timeout=3.0)

    assert not thread.is_alive()
    assert errors == []


def test_video_source_track_cache_reuses_same_key_until_session_end():
    track1 = create_video_source_track(_video_callback, key="video")
    track2 = create_video_source_track(_video_callback, key="video")
    track3 = create_video_source_track(_video_callback, key="other-video")

    assert track2 is track1
    assert track3 is not track1
    assert getattr(track1, "_streamlit_webrtc_lifecycle_scope") == "webrtc-session"


def test_audio_source_track_cache_reuses_same_key_until_session_end():
    track1 = create_audio_source_track(_audio_callback, key="audio")
    track2 = create_audio_source_track(_audio_callback, key="audio")
    track3 = create_audio_source_track(_audio_callback, key="other-audio")

    assert track2 is track1
    assert track3 is not track1
    assert getattr(track1, "_streamlit_webrtc_lifecycle_scope") == "webrtc-session"


def test_pcm_audio_source_cache_reuses_same_key_until_session_end():
    source1 = create_pcm_audio_source_track(key="pcm", sample_rate=48000)
    source2 = create_pcm_audio_source_track(key="pcm", sample_rate=48000)
    source3 = create_pcm_audio_source_track(key="other-pcm", sample_rate=48000)

    assert source2 is source1
    assert source3 is not source1
    assert getattr(source1.track, "_streamlit_webrtc_lifecycle_scope") == (
        "webrtc-session"
    )


def test_sink_track_cache_reuses_same_key_until_session_end():
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
    assert getattr(video1, "_streamlit_webrtc_lifecycle_scope") == "webrtc-session"
    assert getattr(audio1, "_streamlit_webrtc_lifecycle_scope") == "webrtc-session"


def test_default_lifecycle_resets_video_source_on_webrtc_session_end():
    track1 = create_video_source_track(_video_callback, key="video")

    assert _reset_factory_cache_on_webrtc_session_end(track1)

    track2 = create_video_source_track(_video_callback, key="video")
    assert track2 is not track1
    assert track1.readyState == "ended"
    assert track2.readyState == "live"
    assert any(observer.stopped for observer in FakeSessionShutdownObserver.instances)


def test_default_lifecycle_resets_audio_source_on_webrtc_session_end():
    track1 = create_audio_source_track(_audio_callback, key="audio")

    assert _reset_factory_cache_on_webrtc_session_end(track1)

    track2 = create_audio_source_track(_audio_callback, key="audio")
    assert track2 is not track1
    assert track1.readyState == "ended"
    assert track2.readyState == "live"
    assert any(observer.stopped for observer in FakeSessionShutdownObserver.instances)


def test_default_lifecycle_resets_pcm_audio_source_on_webrtc_session_end():
    source1 = create_pcm_audio_source_track(key="pcm", sample_rate=48000)

    assert _reset_factory_cache_on_webrtc_session_end(source1.track)

    source2 = create_pcm_audio_source_track(key="pcm", sample_rate=48000)
    assert source2 is not source1
    assert source1.track.readyState == "ended"
    assert source2.track.readyState == "live"
    assert any(observer.stopped for observer in FakeSessionShutdownObserver.instances)


def test_default_lifecycle_resets_sink_tracks_on_webrtc_session_end():
    video1 = create_video_sink_track(_sink_callback, key="video-sink")
    audio1 = create_audio_sink_track(_sink_callback, key="audio-sink")

    assert _reset_factory_cache_on_webrtc_session_end(video1)
    assert _reset_factory_cache_on_webrtc_session_end(audio1)

    video2 = create_video_sink_track(_sink_callback, key="video-sink")
    audio2 = create_audio_sink_track(_sink_callback, key="audio-sink")
    assert video2 is not video1
    assert audio2 is not audio1
    assert video1.readyState == "new"
    assert audio1.readyState == "new"
    assert any(observer.stopped for observer in FakeSessionShutdownObserver.instances)


def test_webrtc_session_reset_uses_captured_session_state_from_worker_thread(
    monkeypatch,
):
    real_session_state = ItemOnlySessionState()
    monkeypatch.setattr(
        factory,
        "get_script_run_ctx",
        lambda: SimpleNamespace(session_state=real_session_state),
    )
    sink1 = create_video_sink_track(_sink_callback, key="video-sink")
    cache_key = factory._VIDEO_SINK_TRACK_CACHE_KEY_PREFIX + "video-sink"
    observer_cache_key = (
        factory._VIDEO_SINK_TRACK_SHUTDOWN_OBSERVER_CACHE_KEY_PREFIX + "video-sink"
    )

    assert real_session_state[cache_key] is sink1
    assert observer_cache_key in real_session_state

    monkeypatch.setattr(factory, "get_script_run_ctx", lambda: None)

    _run_in_thread(lambda: _reset_factory_cache_on_webrtc_session_end(sink1))

    assert cache_key not in real_session_state
    assert observer_cache_key not in real_session_state

    monkeypatch.setattr(
        factory,
        "get_script_run_ctx",
        lambda: SimpleNamespace(session_state=real_session_state),
    )
    sink2 = create_video_sink_track(_sink_callback, key="video-sink")

    assert sink2 is not sink1


def test_shutdown_observer_reset_uses_captured_session_state_from_polling_thread(
    monkeypatch,
):
    real_session_state = ItemOnlySessionState()
    monkeypatch.setattr(
        factory,
        "get_script_run_ctx",
        lambda: SimpleNamespace(session_state=real_session_state),
    )
    sink1 = create_video_sink_track(_sink_callback, key="video-sink")
    cache_key = factory._VIDEO_SINK_TRACK_CACHE_KEY_PREFIX + "video-sink"
    observer_cache_key = (
        factory._VIDEO_SINK_TRACK_SHUTDOWN_OBSERVER_CACHE_KEY_PREFIX + "video-sink"
    )
    observer = real_session_state[observer_cache_key]

    monkeypatch.setattr(factory, "get_script_run_ctx", lambda: None)

    _run_in_thread(observer.callback)

    assert cache_key not in real_session_state
    assert observer_cache_key not in real_session_state

    monkeypatch.setattr(
        factory,
        "get_script_run_ctx",
        lambda: SimpleNamespace(session_state=real_session_state),
    )
    sink2 = create_video_sink_track(_sink_callback, key="video-sink")

    assert sink2 is not sink1


def test_streamlit_session_lifecycle_opts_out_of_webrtc_session_reset():
    track1 = create_video_source_track(
        _video_callback,
        key="video",
        lifecycle_scope="streamlit-session",
    )

    assert not _reset_factory_cache_on_webrtc_session_end(track1)

    track2 = create_video_source_track(
        _video_callback,
        key="video",
        lifecycle_scope="streamlit-session",
    )
    assert track2 is track1
    assert track1.readyState == "live"


def test_lifecycle_scope_can_be_updated_on_reuse():
    track1 = create_video_source_track(
        _video_callback,
        key="video",
        lifecycle_scope="streamlit-session",
    )
    track2 = create_video_source_track(
        _video_callback,
        key="video",
        lifecycle_scope="webrtc-session",
    )

    assert track2 is track1
    assert _reset_factory_cache_on_webrtc_session_end(track1)


def test_invalid_lifecycle_scope_is_rejected():
    with pytest.raises(ValueError, match="lifecycle_scope"):
        create_video_source_track(
            _video_callback,
            key="video",
            lifecycle_scope="invalid",  # type: ignore[arg-type]
        )
