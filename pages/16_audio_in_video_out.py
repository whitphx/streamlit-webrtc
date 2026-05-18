"""Audio-in / video-out SENDRECV demo.

The browser captures audio only, the server consumes those audio frames
through an `audio_frame_callback`, and a server-generated video track is
streamed back. Demonstrates that one-sided SENDRECV (peer sends one kind,
server emits the other via `source_*_track`) is supported.
"""

import fractions
import threading
import time

import av
import cv2
import numpy as np
import streamlit as st
from streamlit_webrtc import (
    WebRtcMode,
    create_video_source_track,
    webrtc_streamer,
)

st.title("Audio In / Video Out")
st.write(
    "The browser sends microphone audio; the server measures its loudness "
    "and streams back a video that visualizes the level. No video is "
    "captured from the browser."
)

# Shared state between the audio callback (driven by the receiving track)
# and the video source callback (driven by the outgoing track). The two
# callbacks run on different threads, so the lock is load-bearing.
_state = {"level": 0.0, "updated_at": 0.0}
_state_lock = threading.Lock()


def audio_frame_callback(frame: av.AudioFrame) -> av.AudioFrame:
    samples = frame.to_ndarray()
    if samples.size:
        rms = float(np.sqrt(np.mean(np.square(samples.astype(np.float32)))))
        # Roughly normalize int16 RMS to 0..1.
        normalized = min(rms / 32768.0, 1.0)
        with _state_lock:
            _state["level"] = normalized
            _state["updated_at"] = time.monotonic()
    return frame


def video_source_callback(pts: int, time_base: fractions.Fraction) -> av.VideoFrame:
    with _state_lock:
        level = _state["level"]
        updated_at = _state["updated_at"]

    height, width = 360, 640
    buf = np.zeros((height, width, 3), dtype=np.uint8)

    # Green bar that fills bottom-up proportional to the audio level.
    bar_h = int(level * height)
    if bar_h > 0:
        buf[height - bar_h :, :, 1] = 220

    cv2.putText(
        buf,
        f"audio level: {level:.3f}",
        (16, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (255, 255, 255),
        2,
    )
    age = time.monotonic() - updated_at if updated_at else float("inf")
    status = "live" if age < 1.0 else "waiting for audio..."
    cv2.putText(
        buf,
        status,
        (16, 76),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (200, 200, 200),
        2,
    )
    return av.VideoFrame.from_ndarray(buf, format="bgr24")


video_source_track = create_video_source_track(
    video_source_callback, key="audio_in_video_out_source", fps=15
)


def on_change() -> None:
    ctx = st.session_state["audio_in_video_out"]
    stopped = not ctx.state.playing and not ctx.state.signalling
    if stopped:
        video_source_track.stop()


webrtc_streamer(
    key="audio_in_video_out",
    mode=WebRtcMode.SENDRECV,
    media_stream_constraints={"audio": True, "video": False},
    source_video_track=video_source_track,
    audio_frame_callback=audio_frame_callback,
    on_change=on_change,
)
