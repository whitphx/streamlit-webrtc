import streamlit as st
from streamlit_webrtc import webrtc_streamer


def video_frame_callback(frame):
    return frame


def on_video_ended():
    st.session_state.pop("my_session_resource", None)


webrtc_streamer(
    key="example",
    video_frame_callback=video_frame_callback,
    on_video_ended=on_video_ended,
)
