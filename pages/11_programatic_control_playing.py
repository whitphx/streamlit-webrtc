"""A sample of controlling the playing state from Python."""

import streamlit as st
from streamlit_webrtc import WebRtcMode, webrtc_streamer

# Page title and introduction
st.title("Programmatic Control")
st.markdown("""
Control the **WebRTC streaming state programmatically** from Python code instead of using the default buttons. 
This demonstrates how to manage streaming state through custom UI elements.

**Features:**
- Programmatic start/stop control
- Custom UI for stream management
- Python-controlled streaming state
- Integration with Streamlit widgets

**Instructions:** Use the checkbox below to control the streaming state!
""")

st.markdown("---")

playing = st.checkbox("Playing", value=True)

webrtc_streamer(
    key="programatic_control",
    desired_playing_state=playing,
    mode=WebRtcMode.SENDRECV,
)
