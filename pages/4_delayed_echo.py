import asyncio
import logging
from typing import List

import av
import streamlit as st
from streamlit_webrtc import WebRtcMode, webrtc_streamer

# Page title and introduction
st.title("Delayed Video Echo")
st.markdown("""
Create a **video delay effect** by buffering video frames and playing them back with a time delay. 
This demonstrates video frame buffering and timing control in real-time video processing.

**How it works:**
- Captures video frames from your camera
- Stores frames in a buffer queue
- Plays back the video with a configurable delay
- Creates a time-delayed video echo effect

**Instructions:** Adjust the delay amount below, then click START to see your delayed video!
""")

st.markdown("---")

logger = logging.getLogger(__name__)


delay = st.slider("Delay", 0.0, 5.0, 1.0, 0.05)


async def queued_video_frames_callback(
    frames: List[av.VideoFrame],
) -> List[av.VideoFrame]:
    logger.debug("Delay: %f", delay)
    # A standalone `await ...` is interpreted as an expression and
    # the Streamlit magic's target, which leads implicit calls of `st.write`.
    # To prevent it, fix it as `_ = await ...`, a statement.
    # See https://discuss.streamlit.io/t/issue-with-asyncio-run-in-streamlit/7745/15
    await asyncio.sleep(delay)
    return frames


async def queued_audio_frames_callback(
    frames: List[av.AudioFrame],
) -> List[av.AudioFrame]:
    await asyncio.sleep(delay)
    return frames


webrtc_streamer(
    key="delay",
    mode=WebRtcMode.SENDRECV,
    queued_video_frames_callback=queued_video_frames_callback,
    queued_audio_frames_callback=queued_audio_frames_callback,
    async_processing=True,
)
