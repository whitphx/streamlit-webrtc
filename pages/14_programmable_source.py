import fractions
import time

import av
import cv2
import numpy as np
import streamlit as st
from streamlit_webrtc import WebRtcMode, create_video_source_track, webrtc_streamer

thickness = st.slider("thickness", 1, 10, 3, 1)


def video_source_callback(pts: int, time_base: fractions.Fraction) -> av.VideoFrame:
    pts_sec = pts * time_base

    buffer = np.zeros((480, 640, 3), dtype=np.uint8)
    buffer = cv2.putText(
        buffer,
        text=f"time: {time.time():.2f}",
        org=(0, 32),
        fontFace=cv2.FONT_HERSHEY_SIMPLEX,
        fontScale=1.0,
        color=(255, 255, 0),
        thickness=thickness,
        lineType=cv2.LINE_4,
    )
    buffer = cv2.putText(
        buffer,
        text=f"pts: {pts} ({float(pts_sec):.2f} sec)",
        org=(0, 64),
        fontFace=cv2.FONT_HERSHEY_SIMPLEX,
        fontScale=1.0,
        color=(255, 255, 0),
        thickness=thickness,
        lineType=cv2.LINE_4,
    )
    return av.VideoFrame.from_ndarray(buffer, format="bgr24")


fps = st.slider("fps", 1, 30, 30, 1)


video_source_track = create_video_source_track(
    video_source_callback, key="video_source_track", fps=fps
)


def on_change():
    ctx = st.session_state["player"]
    stopped = not ctx.state.playing and not ctx.state.signalling
    if stopped:
        video_source_track.stop()  # Manually stop the track.


webrtc_streamer(
    key="player",
    mode=WebRtcMode.RECVONLY,
    source_video_track=video_source_track,
    media_stream_constraints={"video": True, "audio": False},
    on_change=on_change,
)
