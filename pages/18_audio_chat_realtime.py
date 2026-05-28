"""Two-way realtime voice chat with OpenAI's Realtime API.

The browser captures microphone audio. The server consumes every
audio frame through ``create_audio_sink_track`` (push-based, no
drop), resamples it to 24 kHz mono PCM16, and streams it to
``gpt-realtime`` over OpenAI's Realtime WebSocket. The model's spoken
response arrives as 24 kHz PCM16 chunks, which are buffered and emitted
back to the browser through ``create_audio_source_track``. Server-side
VAD on OpenAI's side handles turn-taking and interruption.

This page doubles as an end-to-end exercise of the ``sink_audio_track``
+ ``source_audio_track`` pair (introduced in #2479) — the primitive
that lets the input rate (browser mic, 48 kHz Opus) and the output
rate (model response, 24 kHz PCM) run on independent clocks without
the 1:1 frame coupling of ``audio_frame_callback``.

Setup:
- ``pip install openai``
- Provide ``OPENAI_API_KEY`` via env var, or paste it into the sidebar.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import threading
from typing import Optional

import av
import numpy as np
import numpy.typing as npt
import streamlit as st
from streamlit_webrtc import (
    WebRtcMode,
    create_audio_sink_track,
    create_audio_source_track,
    webrtc_streamer,
)
from streamlit_webrtc.shutdown import SessionShutdownObserver

logger = logging.getLogger(__name__)

# OpenAI's Realtime API speaks PCM16 mono at 24 kHz on both sides. Our
# resampler converts incoming Opus-decoded frames (48 kHz, possibly
# stereo) down to this rate; we also emit response audio at this rate
# and let aiortc/PyAV upsample to 48 kHz Opus for the outgoing
# transceiver.
TARGET_SAMPLE_RATE = 24000
SOURCE_PTIME = 0.020
SOURCE_SAMPLES_PER_FRAME = int(TARGET_SAMPLE_RATE * SOURCE_PTIME)

DEFAULT_MODEL = "gpt-realtime"
DEFAULT_VOICE = "alloy"
VOICE_OPTIONS = [
    "alloy",
    "ash",
    "ballad",
    "coral",
    "echo",
    "sage",
    "shimmer",
    "verse",
]
DEFAULT_INSTRUCTIONS = (
    "You are a friendly assistant demoing the streamlit-webrtc library. "
    "Keep replies short — one or two sentences."
)


class _PcmRingBuffer:
    """Thread-safe int16 mono PCM buffer with silence-padded pulls.

    Wraps :class:`av.AudioFifo` (FFmpeg's ``AVAudioFifo``) so the
    producer/consumer split inherits FFmpeg's tested partial-read
    semantics. The OpenAI session thread pushes irregular-sized chunks
    as they arrive in ``response.output_audio.delta`` events; the
    aiortc source callback pulls fixed-size frames at the playback
    cadence. If the model hasn't sent enough audio yet the pull is
    padded with silence so the source track stays on schedule.
    """

    def __init__(self) -> None:
        # PyAV's AudioFifo is not documented thread-safe, and we have a
        # producer thread (OpenAI session) and consumer thread (aiortc
        # source callback) hitting it concurrently.
        self._fifo = av.AudioFifo()
        self._lock = threading.Lock()

    def push(self, samples: npt.NDArray[np.int16]) -> None:
        frame = av.AudioFrame.from_ndarray(
            samples.reshape(1, -1), format="s16", layout="mono"
        )
        frame.sample_rate = TARGET_SAMPLE_RATE
        with self._lock:
            self._fifo.write(frame)

    def pull(self, n: int) -> npt.NDArray[np.int16]:
        with self._lock:
            frame = self._fifo.read(n, partial=True)
        out = np.zeros(n, dtype=np.int16)
        if frame is not None:
            available = frame.to_ndarray().reshape(-1)
            out[: available.shape[0]] = available
        return out

    def clear(self) -> None:
        with self._lock:
            self._fifo = av.AudioFifo()


class RealtimeBridge:
    """Owns the OpenAI Realtime WebSocket and the I/O bridges.

    Runs the session on a private asyncio loop in a background thread so
    a slow event-receive or network blip can't backpressure the aiortc
    media loop. The two cross-thread bridges are:

    * **Input** (aiortc loop → session thread): the sink callback
      resamples each browser audio frame to 24 kHz PCM16 and calls
      :meth:`push_input` — bytes hop onto the session loop's queue via
      ``call_soon_threadsafe``.
    * **Output** (session thread → aiortc loop): the session thread
      decodes ``response.output_audio.delta`` chunks and writes them
      into a :class:`_PcmRingBuffer`; the source callback pulls
      fixed-size slices each tick.
    """

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        voice: str = DEFAULT_VOICE,
        instructions: str = DEFAULT_INSTRUCTIONS,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._voice = voice
        self._instructions = instructions

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._input_queue: Optional["asyncio.Queue[bytes]"] = None
        self._output_buffer = _PcmRingBuffer()
        # av.AudioResampler buffers internally, so calling resample() on
        # each input frame yields zero-or-more output frames at the
        # target rate. The instance is stateful and must not be shared
        # across reset/restart of the session.
        self._resampler = av.AudioResampler(
            format="s16", layout="mono", rate=TARGET_SAMPLE_RATE
        )

        self._thread: Optional[threading.Thread] = None
        self._stop_event: Optional[asyncio.Event] = None
        # Set when the session loop is ready to accept call_soon_threadsafe.
        self._ready_event = threading.Event()

        self._state_lock = threading.Lock()
        self._user_transcript: str = ""
        self._assistant_transcript: str = ""
        self._error: Optional[str] = None
        self._connected: bool = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    @property
    def is_running(self) -> bool:
        t = self._thread
        return t is not None and t.is_alive()

    def start(self) -> None:
        if self.is_running:
            return
        # A dead thread (e.g. after a session crash) is replaced; the
        # caller can then act on the `error` snapshot to decide whether
        # to retry.
        self._ready_event.clear()
        self._thread = threading.Thread(
            target=self._run, name="OpenAIRealtimeBridge", daemon=True
        )
        self._thread.start()
        # Wait for the loop to be installed so push_input can safely
        # call_soon_threadsafe from the very first frame.
        self._ready_event.wait(timeout=3.0)

    def stop(self) -> None:
        loop, stop_event = self._loop, self._stop_event
        if loop is not None and stop_event is not None and not loop.is_closed():
            loop.call_soon_threadsafe(stop_event.set)
        thread = self._thread
        if thread is not None:
            thread.join(timeout=3.0)
        self._thread = None
        self._output_buffer.clear()

    # ------------------------------------------------------------------
    # Called from aiortc loop
    # ------------------------------------------------------------------
    def push_input(self, frame: av.AudioFrame) -> None:
        loop, q = self._loop, self._input_queue
        if loop is None or q is None or loop.is_closed():
            return
        for resampled in self._resampler.resample(frame):
            arr = resampled.to_ndarray()
            # `s16` mono frames come back as shape (1, samples).
            pcm_bytes = arr.astype(np.int16, copy=False).tobytes()
            if not pcm_bytes:
                continue
            try:
                loop.call_soon_threadsafe(q.put_nowait, pcm_bytes)
            except RuntimeError:
                # Loop just shut down underneath us; drop the frame.
                return

    def pull_output(self, n_samples: int) -> np.ndarray:
        return self._output_buffer.pull(n_samples)

    # ------------------------------------------------------------------
    # Status (for the UI)
    # ------------------------------------------------------------------
    def snapshot(self) -> dict:
        with self._state_lock:
            return {
                "user": self._user_transcript,
                "assistant": self._assistant_transcript,
                "error": self._error,
                "connected": self._connected,
            }

    # ------------------------------------------------------------------
    # Background-thread session
    # ------------------------------------------------------------------
    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        try:
            self._input_queue = asyncio.Queue(maxsize=256)
            self._stop_event = asyncio.Event()
            self._ready_event.set()
            loop.run_until_complete(self._session())
        except Exception as exc:
            logger.exception("Realtime session crashed")
            with self._state_lock:
                self._error = f"{type(exc).__name__}: {exc}"
        finally:
            with self._state_lock:
                self._connected = False
            try:
                loop.close()
            finally:
                self._loop = None

    async def _session(self) -> None:
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise RuntimeError(
                "Install the OpenAI SDK to use this demo: pip install openai"
            ) from exc

        if self._stop_event is None or self._input_queue is None:
            raise RuntimeError("Bridge loop not initialized")
        stop_event = self._stop_event

        client = AsyncOpenAI(api_key=self._api_key)
        async with client.realtime.connect(model=self._model) as conn:
            await conn.session.update(
                session={
                    "type": "realtime",
                    "model": self._model,
                    "instructions": self._instructions,
                    "audio": {
                        "input": {
                            "turn_detection": {"type": "server_vad"},
                        },
                        "output": {"voice": self._voice},
                    },
                }
            )
            with self._state_lock:
                self._connected = True

            tasks = [
                asyncio.create_task(self._send_loop(conn), name="realtime-send"),
                asyncio.create_task(self._recv_loop(conn), name="realtime-recv"),
                asyncio.create_task(stop_event.wait(), name="realtime-stop"),
            ]
            try:
                await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            finally:
                for t in tasks:
                    t.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_loop(self, conn) -> None:
        if self._input_queue is None:
            return
        while True:
            pcm = await self._input_queue.get()
            await conn.input_audio_buffer.append(
                audio=base64.b64encode(pcm).decode("ascii")
            )

    async def _recv_loop(self, conn) -> None:
        async for event in conn:
            etype = getattr(event, "type", "")
            if etype == "response.output_audio.delta":
                pcm = base64.b64decode(event.delta)
                samples = np.frombuffer(pcm, dtype=np.int16)
                self._output_buffer.push(samples)
            elif etype == "input_audio_buffer.speech_started":
                # Barge-in: drop any pending model audio so the user's
                # new utterance isn't talked over while we wait for the
                # next response.
                self._output_buffer.clear()
            elif etype == "response.output_audio_transcript.delta":
                with self._state_lock:
                    self._assistant_transcript += getattr(event, "delta", "") or ""
            elif etype == "response.done":
                with self._state_lock:
                    if (
                        self._assistant_transcript
                        and not self._assistant_transcript.endswith("\n")
                    ):
                        self._assistant_transcript += "\n"
            elif etype == "conversation.item.input_audio_transcription.delta":
                with self._state_lock:
                    self._user_transcript += getattr(event, "delta", "") or ""
            elif etype == "conversation.item.input_audio_transcription.completed":
                with self._state_lock:
                    if self._user_transcript and not self._user_transcript.endswith(
                        "\n"
                    ):
                        self._user_transcript += "\n"
            elif etype == "error":
                err = getattr(event, "error", None)
                msg = getattr(err, "message", None) or repr(err)
                logger.warning("Realtime API error: %s", msg)
                with self._state_lock:
                    self._error = msg


# ----------------------------------------------------------------------
# UI
# ----------------------------------------------------------------------

st.title("Realtime Voice Chat (OpenAI Realtime API)")
st.write(
    "Speak into your microphone and the model talks back in real time. "
    "Audio in / audio out flow through the same WebRTC session, with "
    "`gpt-realtime` brokering the conversation server-side."
)

with st.sidebar:
    st.header("OpenAI Realtime settings")
    api_key = st.text_input(
        "OPENAI_API_KEY",
        value=os.environ.get("OPENAI_API_KEY", ""),
        type="password",
        help="Stays on the server. Not sent to the browser.",
    )
    model = st.text_input("Model", value=DEFAULT_MODEL)
    voice = st.selectbox(
        "Voice", VOICE_OPTIONS, index=VOICE_OPTIONS.index(DEFAULT_VOICE)
    )
    instructions = st.text_area(
        "System instructions",
        value=DEFAULT_INSTRUCTIONS,
        height=140,
    )

if not api_key:
    st.info("Enter your `OPENAI_API_KEY` in the sidebar (or set the env var) to begin.")
    st.stop()

# One bridge per Streamlit session, cached so reruns reuse it. The
# shutdown observer hands off `bridge.stop()` to the runtime so the
# WebSocket and thread are released when the user closes the page —
# `on_change` only fires on the Stop button.
BRIDGE_KEY = "openai_realtime_bridge"
BRIDGE_SHUTDOWN_OBSERVER_KEY = "openai_realtime_bridge_shutdown_observer"


def _get_or_make_bridge() -> RealtimeBridge:
    bridge = st.session_state.get(BRIDGE_KEY)
    # Reconfigure on any setting change by tearing down and rebuilding;
    # the sidebar widgets are cheap to recreate from.
    config = (api_key, model, voice, instructions)
    if bridge is not None and st.session_state.get("_bridge_config") != config:
        bridge.stop()
        bridge = None
    if bridge is None:
        old_observer = st.session_state.get(BRIDGE_SHUTDOWN_OBSERVER_KEY)
        if isinstance(old_observer, SessionShutdownObserver):
            old_observer.stop()
        bridge = RealtimeBridge(
            api_key=api_key, model=model, voice=voice, instructions=instructions
        )
        st.session_state[BRIDGE_KEY] = bridge
        st.session_state["_bridge_config"] = config
        st.session_state[BRIDGE_SHUTDOWN_OBSERVER_KEY] = SessionShutdownObserver(
            bridge.stop
        )
    return bridge


bridge = _get_or_make_bridge()


def audio_sink_callback(frame: av.AudioFrame) -> None:
    bridge.push_input(frame)


def audio_source_callback(pts, time_base) -> av.AudioFrame:
    samples = bridge.pull_output(SOURCE_SAMPLES_PER_FRAME)
    # av.AudioFrame.from_ndarray expects shape (channels, samples) for
    # non-planar `s16` mono.
    frame = av.AudioFrame.from_ndarray(
        samples.reshape(1, -1), format="s16", layout="mono"
    )
    frame.sample_rate = TARGET_SAMPLE_RATE
    return frame


audio_sink_track = create_audio_sink_track(
    audio_sink_callback, key="openai_realtime_in"
)
audio_source_track = create_audio_source_track(
    audio_source_callback,
    key="openai_realtime_out",
    sample_rate=TARGET_SAMPLE_RATE,
    ptime=SOURCE_PTIME,
)


def on_change() -> None:
    ctx = st.session_state["openai_realtime_chat"]
    if ctx.state.playing and not bridge.is_running:
        bridge.start()
    stopped = not ctx.state.playing and not ctx.state.signalling
    if stopped:
        bridge.stop()
        audio_sink_track.stop()
        audio_source_track.stop()


webrtc_streamer(
    key="openai_realtime_chat",
    mode=WebRtcMode.SENDRECV,
    media_stream_constraints={"audio": True, "video": False},
    sink_audio_track=audio_sink_track,
    source_audio_track=audio_source_track,
    on_change=on_change,
)


# The bridge updates `_error` and the transcripts on its own thread; if
# we rendered them at top-level they'd only refresh when the script
# reruns (e.g. on Stop), so a session-crashing error would stay hidden
# while the user kept speaking. A 500 ms fragment polls the bridge's
# snapshot for live status without re-running the whole page.
@st.fragment(run_every="500ms")
def render_live_status() -> None:
    snap = bridge.snapshot()
    if snap["error"]:
        st.error(f"Realtime API error: {snap['error']}")
    if snap["user"] or snap["assistant"]:
        st.subheader("Transcript")
        col_u, col_a = st.columns(2)
        with col_u:
            st.caption("You")
            st.text(snap["user"] or "—")
        with col_a:
            st.caption("Assistant")
            st.text(snap["assistant"] or "—")


render_live_status()

st.caption(
    "Audio path: browser mic → 48 kHz Opus → aiortc decode → "
    "`audio_sink_track` callback → resample 24 kHz s16 → OpenAI WS. "
    "Model audio: WS → 24 kHz s16 PCM ring → `audio_source_track` "
    "callback → aiortc Opus encode → browser speaker."
)
