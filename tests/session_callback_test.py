import asyncio
import concurrent.futures
import fractions
import threading
import time
from typing import Any, Dict, List, Optional

import av
import numpy as np
import pytest
import streamlit as st
from aiortc import MediaStreamTrack, RTCPeerConnection
from aiortc.contrib.media import MediaRelay
from streamlit.runtime.fragment import MemoryFragmentStorage
from streamlit.runtime.memory_uploaded_file_manager import MemoryUploadedFileManager
from streamlit.runtime.pages_manager import PagesManager
from streamlit.runtime.state import SafeSessionState, SessionState

from streamlit_webrtc._compat import (
    ScriptRunContext,
    add_script_run_ctx,
    get_script_run_ctx,
)
from streamlit_webrtc.models import CallbackAttachableProcessor
from streamlit_webrtc.process import AudioProcessTrack
from streamlit_webrtc.session_callback import (
    call_with_script_run_ctx,
    run_ended_callback,
)
from streamlit_webrtc.sink import AudioSinkTrack
from streamlit_webrtc.source import AudioSourceTrack, VideoSourceTrack
from streamlit_webrtc.webrtc import WebRtcMode, WebRtcWorker


def _make_ctx(session_id: str) -> ScriptRunContext:
    sent: List[Any] = []
    ctx = ScriptRunContext(
        session_id=session_id,
        _enqueue=sent.append,
        query_string="",
        session_state=SafeSessionState(SessionState(), lambda: None),
        uploaded_file_mgr=MemoryUploadedFileManager("/mock/upload"),
        main_script_path="",
        user_info={"email": "test@example.com"},
        fragment_storage=MemoryFragmentStorage(),
        pages_manager=PagesManager(""),
    )
    # Exposed so tests can check that nothing reached the browser queue.
    ctx.sent = sent  # type: ignore[attr-defined]
    return ctx


def _audio_frame(pts: int = 0) -> av.AudioFrame:
    frame = av.AudioFrame.from_ndarray(
        np.zeros((1, 960), dtype=np.int16), format="s16", layout="mono"
    )
    frame.sample_rate = 48000
    frame.pts = pts
    frame.time_base = fractions.Fraction(1, 48000)
    return frame


class _IdleAudioTrack(MediaStreamTrack):
    kind = "audio"

    async def recv(self):  # pragma: no cover - never pulled
        await asyncio.sleep(3600)


def _audio_process_track(
    on_ended, ctx: Optional[ScriptRunContext]
) -> AudioProcessTrack:
    processor = CallbackAttachableProcessor[av.AudioFrame](None, None, on_ended)
    return AudioProcessTrack(_IdleAudioTrack(), processor, script_run_ctx=ctx)


def test_session_state_write_reaches_registering_session() -> None:
    ctx = _make_ctx("session-a")
    done = threading.Event()

    def on_ended() -> None:
        st.session_state["ended"] = True
        done.set()

    _audio_process_track(on_ended, ctx).stop()

    assert done.wait(timeout=5)
    assert ctx.session_state["ended"] is True


def test_two_sessions_do_not_see_each_others_state() -> None:
    ctx_a = _make_ctx("session-a")
    ctx_b = _make_ctx("session-b")
    ctx_a.session_state["mine"] = "a"
    ctx_b.session_state["mine"] = "b"
    seen: Dict[str, str] = {}
    done = threading.Barrier(3)

    def make_callback(name: str):
        def on_ended() -> None:
            seen[name] = st.session_state["mine"]
            st.session_state[f"written_by_{name}"] = True
            done.wait(timeout=5)

        return on_ended

    _audio_process_track(make_callback("a"), ctx_a).stop()
    _audio_process_track(make_callback("b"), ctx_b).stop()
    done.wait(timeout=5)

    assert seen == {"a": "a", "b": "b"}
    assert "written_by_b" not in ctx_a.session_state
    assert "written_by_a" not in ctx_b.session_state


@pytest.mark.asyncio
async def test_slow_callback_does_not_block_event_loop() -> None:
    ctx = _make_ctx("session-a")
    finished = threading.Event()

    def on_ended() -> None:
        time.sleep(1.0)
        finished.set()

    track = _audio_process_track(on_ended, ctx)

    ticks: List[float] = []

    async def ticker() -> None:
        while not finished.is_set():
            ticks.append(time.monotonic())
            await asyncio.sleep(0.02)

    ticker_task = asyncio.create_task(ticker())
    await asyncio.sleep(0.05)
    started = time.monotonic()
    track.stop()
    assert time.monotonic() - started < 0.2
    await ticker_task

    assert finished.is_set()
    gaps = [b - a for a, b in zip(ticks, ticks[1:])]
    assert max(gaps) < 0.3


def test_callback_thread_context_is_cleared_after_call() -> None:
    ctx = _make_ctx("session-a")
    done = threading.Event()
    seen: Dict[str, Any] = {}

    def on_ended() -> None:
        seen["thread"] = threading.current_thread()
        seen["session_id"] = get_script_run_ctx().session_id  # type: ignore[union-attr]
        done.set()

    _audio_process_track(on_ended, ctx).stop()
    assert done.wait(timeout=5)
    seen["thread"].join(timeout=5)

    assert seen["session_id"] == "session-a"
    assert getattr(seen["thread"], "streamlit_script_run_ctx", None) is None


def test_pooled_thread_context_is_restored_after_call() -> None:
    # The native backend calls `on_ended` on asyncio's default executor,
    # whose threads are reused by unrelated work afterwards.
    ctx = _make_ctx("session-a")
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        executor.submit(call_with_script_run_ctx, lambda: None, ctx).result()
        after = executor.submit(get_script_run_ctx, True).result()

    assert after is None


def test_callback_for_a_discarded_session_does_not_raise() -> None:
    # The session is not registered with the Runtime, as after Streamlit
    # drops a disconnected session.
    ctx = _make_ctx("gone")
    done = threading.Event()
    reached_end = threading.Event()

    def on_ended() -> None:
        try:
            st.session_state["ended"] = True
            st.write("not rendered")
            st.rerun()
            reached_end.set()
        finally:
            done.set()

    _audio_process_track(on_ended, ctx).stop()

    assert done.wait(timeout=5)
    assert reached_end.is_set()
    assert ctx.sent == []  # type: ignore[attr-defined]


def test_sink_on_ended_runs_off_the_loop_with_session_state() -> None:
    ctx = _make_ctx("session-a")
    done = threading.Event()
    seen: Dict[str, Any] = {}

    def on_ended() -> None:
        seen["thread"] = threading.current_thread()
        st.session_state["sink_ended"] = True
        done.set()

    sink = AudioSinkTrack(callback=lambda frame: None)
    sink._on_ended_callback = on_ended
    sink._on_ended_script_run_ctx = ctx
    sink._fire_on_ended()

    assert done.wait(timeout=5)
    assert seen["thread"] is not threading.current_thread()
    assert ctx.session_state["sink_ended"] is True


def test_source_stopped_on_its_session_script_thread_runs_inline() -> None:
    ctx = _make_ctx("session-a")
    calls: List[threading.Thread] = []
    track = VideoSourceTrack(callback=lambda pts, tb: None, fps=30)  # type: ignore[arg-type,return-value]
    track._on_ended_callback = lambda: calls.append(threading.current_thread())
    track._on_ended_script_run_ctx = ctx

    calls_when_stop_returned: List[threading.Thread] = []

    def script_thread() -> None:
        track.stop()
        calls_when_stop_returned.extend(calls)

    thread = add_script_run_ctx(threading.Thread(target=script_thread), ctx)
    thread.start()
    thread.join(timeout=5)

    assert calls_when_stop_returned == [thread]


def test_errors_in_the_callback_are_logged(caplog) -> None:
    done = threading.Event()

    def boom() -> None:
        done.set()
        raise RuntimeError("boom")

    run_ended_callback(boom, None, owner="Test")
    assert done.wait(timeout=5)
    deadline = time.monotonic() + 5
    while "on_ended callback raised" not in caplog.text:
        assert time.monotonic() < deadline
        time.sleep(0.01)


def _audio_source_callback(pts: int, time_base: fractions.Fraction) -> av.AudioFrame:
    return _audio_frame(pts)


_WORKER_DEFAULTS: Dict[str, Any] = dict(
    rtc_configuration=None,
    source_video_track=None,
    source_audio_track=None,
    sink_video_track=None,
    sink_audio_track=None,
    player_factory=None,
    in_recorder_factory=None,
    out_recorder_factory=None,
    video_frame_callback=None,
    audio_frame_callback=None,
    queued_video_frames_callback=None,
    queued_audio_frames_callback=None,
    on_video_ended=None,
    video_processor_factory=None,
    audio_processor_factory=None,
    async_processing=True,
    video_receiver_size=4,
    audio_receiver_size=4,
    sendback_video=True,
    sendback_audio=True,
)


@pytest.mark.asyncio
async def test_on_audio_ended_writes_session_state_when_the_peer_leaves() -> None:
    """Loopback: the browser side closes, as when the tab is closed."""
    loop = asyncio.get_running_loop()
    ctx = _make_ctx("session-a")
    ended = threading.Event()
    frames: List[int] = []

    def audio_frame_callback(frame: av.AudioFrame) -> av.AudioFrame:
        frames.append(1)
        return frame

    def on_audio_ended() -> None:
        st.session_state["audio_ended"] = True
        ended.set()

    def create_worker_on_script_thread() -> WebRtcWorker:
        add_script_run_ctx(threading.current_thread(), ctx)
        try:
            return WebRtcWorker(
                loop=loop,
                relay=MediaRelay(),
                mode=WebRtcMode.SENDRECV,
                **{
                    **_WORKER_DEFAULTS,
                    "audio_frame_callback": audio_frame_callback,
                    "on_audio_ended": on_audio_ended,
                },
            )
        finally:
            setattr(threading.current_thread(), "streamlit_script_run_ctx", None)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        worker = await loop.run_in_executor(executor, create_worker_on_script_thread)

    client = RTCPeerConnection()
    client.addTrack(AudioSourceTrack(_audio_source_callback, sample_rate=48000))

    @client.on("icecandidate")  # type: ignore[arg-type]
    async def _to_worker(c):  # pragma: no cover - aiortc-driven
        if c is not None:
            worker.add_ice_candidate(c)

    try:
        await client.setLocalDescription(await client.createOffer())
        assert client.localDescription is not None
        answer = await asyncio.to_thread(
            worker.process_offer,
            client.localDescription.sdp,
            client.localDescription.type,
            10,
        )
        await client.setRemoteDescription(answer)

        deadline = loop.time() + 15
        while not frames and loop.time() < deadline:
            await asyncio.sleep(0.1)
        assert frames

        await client.close()
        assert await asyncio.to_thread(ended.wait, 15)
        assert ctx.session_state["audio_ended"] is True
    finally:
        await asyncio.to_thread(worker.stop, 1.0)
        await client.close()
        await asyncio.sleep(0.2)
