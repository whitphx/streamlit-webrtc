import time

import av
import cv2
import numpy as np
import streamlit as st
from streamlit_webrtc import WebRtcMode, create_source_video_track, webrtc_streamer

thickness = st.slider("thickness", 1, 10, 3, 1)


def callback():
    buffer = np.zeros((480, 640, 3), dtype=np.uint8)
    buffer = cv2.putText(
        buffer,
        text=str(time.time()),
        org=(0, 32),
        fontFace=cv2.FONT_HERSHEY_SIMPLEX,
        fontScale=1.0,
        color=(255, 255, 0),
        thickness=thickness,
        lineType=cv2.LINE_4,
    )
    return av.VideoFrame.from_ndarray(buffer, format="bgr24")


video_source_track = create_source_video_track(callback, key="video_source_track")


def on_change():
    ctx = st.session_state.sample
    if (
        not ctx.state.playing
        and not ctx.state.signalling
        and video_source_track.readyState == "live"
    ):
        video_source_track.stop()


webrtc_streamer(
    key="sample",
    mode=WebRtcMode.RECVONLY,
    source_video_track=video_source_track,
    media_stream_constraints={"video": True, "audio": False},
    on_change=on_change,  # XXX: The track needs to be stopped manually.
)
