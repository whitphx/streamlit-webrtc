"""A sample to configure MediaStreamConstraints object"""

import streamlit as st
from streamlit_webrtc import WebRtcMode, webrtc_streamer

# Page title and introduction
st.title("Media Constraints Configuration")
st.markdown("""
Configure **MediaStreamConstraints** to control camera and microphone settings. 
This demo shows how to set specific media parameters like frame rate, resolution, and quality.

**Features:**
- Custom video frame rate settings
- Media stream constraint configuration
- Camera/microphone parameter control
- WebRTC media stream optimization

**Instructions:** This demo uses a custom frame rate of 5 FPS. Click START to see the effect!
""")

st.markdown("---")

frame_rate = 5
webrtc_streamer(
    key="media-constraints",
    mode=WebRtcMode.SENDRECV,
    media_stream_constraints={
        "video": {"frameRate": {"ideal": frame_rate}},
    },
    video_html_attrs={
        "style": {"width": "50%", "margin": "0 auto", "border": "5px yellow solid"},
        "controls": False,
        "autoPlay": True,
    },
)
st.write(f"The frame rate is set as {frame_rate}. Video style is changed.")
