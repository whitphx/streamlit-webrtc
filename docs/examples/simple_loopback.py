import streamlit as st
from streamlit_webrtc import webrtc_streamer

st.title("Quick Start Example")

# Stream live video and audio from user's camera and microphone
webrtc_streamer(key="example")
