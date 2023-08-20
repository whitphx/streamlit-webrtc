import time

import cv2
import numpy as np
import streamlit as st
from streamlit_webrtc import VideoSourceTrack, WebRtcMode, webrtc_streamer

init_buffer = np.zeros((480, 640, 3), dtype=np.uint8)


if "video_source_track" not in st.session_state:
    st.session_state.video_source_track = VideoSourceTrack(init_buffer=init_buffer)
video_source_track = st.session_state.video_source_track


ctx = webrtc_streamer(
    key="sample",
    mode=WebRtcMode.RECVONLY,
    source_video_track=video_source_track,
    media_stream_constraints={"video": True, "audio": False},
)

while ctx.state.playing:
    buffer = np.zeros((480, 640, 3), dtype=np.uint8)
    buffer = cv2.putText(
        buffer,
        text=str(time.time()),
        org=(0, 32),
        fontFace=cv2.FONT_HERSHEY_SIMPLEX,
        fontScale=1.0,
        color=(255, 255, 0),
        thickness=2,
        lineType=cv2.LINE_4,
    )
    video_source_track.set_buffer(buffer)
    time.sleep(0.03)
