"""Decoupled video-in / video-out at independent FPS.

The browser captures and sends video at whatever rate ``getUserMedia``
delivers (typically 30 fps). The server consumes every incoming frame
through a ``sink_video_track`` (no drop, callback-based) — useful for
e.g. feeding every frame to an ML model that records its results. The
server then streams *a different* video back at 5 fps via a
``source_video_track``, decoupled from the input rate.

This is the pattern PR #2461 enabled at the SDP layer but couldn't be
expressed cleanly with the old API: ``video_frame_callback`` couples
input to output 1:1, and ``video_receiver`` drops on overflow. The sink
fills the gap.
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
    create_video_sink_track,
    create_video_source_track,
    webrtc_streamer,
)

st.title("Video In / Video Out (Independent FPS)")
st.write(
    "The browser sends camera video. The server counts every received "
    "frame (no drop) and streams back a server-rendered video at 5 fps "
    "showing the running tally."
)

_state_lock = threading.Lock()
_frames_seen = 0
_last_size: tuple[int, int] = (0, 0)
_updated_at = 0.0


def video_sink_callback(frame: av.VideoFrame) -> None:
    # In a real app this is where you'd feed `frame` to a model, persist
    # it, push it onto a queue, etc. Whatever you do, every browser frame
    # reaches this callback in order — no drop.
    global _frames_seen, _last_size, _updated_at
    with _state_lock:
        _frames_seen += 1
        _last_size = (frame.width, frame.height)
        _updated_at = time.monotonic()


def video_source_callback(pts: int, time_base: fractions.Fraction) -> av.VideoFrame:
    with _state_lock:
        frames_seen = _frames_seen
        last_w, last_h = _last_size
        updated_at = _updated_at

    height, width = 360, 640
    buf = np.zeros((height, width, 3), dtype=np.uint8)
    cv2.putText(
        buf,
        f"frames received: {frames_seen}",
        (16, 60),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (255, 255, 255),
        2,
    )
    cv2.putText(
        buf,
        f"input size: {last_w}x{last_h}",
        (16, 110),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (200, 200, 200),
        2,
    )
    age = time.monotonic() - updated_at if updated_at else float("inf")
    status = "live" if age < 1.0 else "waiting for input..."
    cv2.putText(
        buf,
        status,
        (16, 150),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (160, 160, 160),
        2,
    )
    return av.VideoFrame.from_ndarray(buf, format="bgr24")


video_sink_track = create_video_sink_track(
    video_sink_callback, key="video_in_video_out_sink"
)
video_source_track = create_video_source_track(
    video_source_callback, key="video_in_video_out_source", fps=5
)


def on_change() -> None:
    ctx = st.session_state["video_in_video_out_decoupled"]
    stopped = not ctx.state.playing and not ctx.state.signalling
    if stopped:
        video_sink_track.stop()
        video_source_track.stop()


webrtc_streamer(
    key="video_in_video_out_decoupled",
    mode=WebRtcMode.SENDRECV,
    media_stream_constraints={"audio": False, "video": True},
    sink_video_track=video_sink_track,
    source_video_track=video_source_track,
    on_change=on_change,
)
