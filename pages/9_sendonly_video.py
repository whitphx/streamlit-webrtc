"""A sample to use WebRTC in sendonly mode to transfer frames
from the browser to the server and to render frames via `st.image`."""

import logging
import queue

import streamlit as st
from streamlit_webrtc import WebRtcMode, webrtc_streamer

# Page title and introduction
st.title("Send-Only Video Demo")
st.markdown("""
Capture video from your camera and send it to the server **without receiving any video back**. 
This is useful for video recording, analysis, or one-way streaming scenarios.

**How it works:**
- Camera video is sent from browser to server
- Server receives and can process video frames
- No video is sent back to the browser
- Captured frames are displayed using Streamlit's image component

**Instructions:** Click START to begin sending video frames from your camera!
""")

st.markdown("---")

logger = logging.getLogger(__name__)


webrtc_ctx = webrtc_streamer(
    key="video-sendonly",
    mode=WebRtcMode.SENDONLY,
    media_stream_constraints={"video": True},
)

image_place = st.empty()

while True:
    if webrtc_ctx.video_receiver:
        try:
            video_frame = webrtc_ctx.video_receiver.get_frame(timeout=1)
        except queue.Empty:
            logger.warning("Queue is empty. Abort.")
            break

        img_rgb = video_frame.to_ndarray(format="rgb24")
        image_place.image(img_rgb)
    else:
        logger.warning("AudioReciver is not set. Abort.")
        break
