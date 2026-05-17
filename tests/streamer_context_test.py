from unittest.mock import Mock

from streamlit_webrtc.component import WebRtcStreamerContext, WebRtcStreamerState


def _make_context(worker):
    return WebRtcStreamerContext(
        worker=worker, state=WebRtcStreamerState(playing=False, signalling=False)
    )


def test_worker_forwarded_returns_none_when_no_worker():
    ctx = _make_context(worker=None)
    assert ctx.video_receiver is None
    assert ctx.audio_receiver is None
    assert ctx.source_video_track is None
    assert ctx.source_audio_track is None
    assert ctx.input_video_track is None
    assert ctx.input_audio_track is None
    assert ctx.output_video_track is None
    assert ctx.output_audio_track is None


def test_worker_forwarded_reads_from_attached_worker():
    worker = Mock()
    worker.video_receiver = "vr"
    worker.audio_receiver = "ar"
    worker.source_video_track = "svt"
    worker.source_audio_track = "sat"
    worker.input_video_track = "ivt"
    worker.input_audio_track = "iat"
    worker.output_video_track = "ovt"
    worker.output_audio_track = "oat"

    ctx = _make_context(worker=worker)

    assert ctx.video_receiver == "vr"
    assert ctx.audio_receiver == "ar"
    assert ctx.source_video_track == "svt"
    assert ctx.source_audio_track == "sat"
    assert ctx.input_video_track == "ivt"
    assert ctx.input_audio_track == "iat"
    assert ctx.output_video_track == "ovt"
    assert ctx.output_audio_track == "oat"


def test_worker_forwarded_returns_none_after_worker_garbage_collected():
    # WebRtcStreamerContext holds the worker via a weakref, so once the
    # original reference goes away, the descriptor should fall back to None
    # just as if no worker had been attached.
    worker = Mock()
    worker.video_receiver = "vr"
    ctx = _make_context(worker=worker)
    assert ctx.video_receiver == "vr"

    del worker
    assert ctx.video_receiver is None
