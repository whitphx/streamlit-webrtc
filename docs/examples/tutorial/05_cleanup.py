import streamlit as st
from streamlit_webrtc import webrtc_streamer

log_file = st.session_state.get("frame_log")
if log_file is None or log_file.closed:
    log_file = open("frames.log", "a")
    st.session_state["frame_log"] = log_file


def video_frame_callback(frame):
    log_file.write(f"{frame.time}\n")
    return frame


def on_video_ended():
    log_file.close()


webrtc_streamer(
    key="example",
    video_frame_callback=video_frame_callback,
    on_video_ended=on_video_ended,
)
