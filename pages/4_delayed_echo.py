import asyncio
import logging
from typing import List

import av
import streamlit as st
from streamlit_webrtc import WebRtcMode, webrtc_streamer

from sample_utils.turn import get_ice_servers

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
    rtc_configuration={"iceServers": get_ice_servers()},
    queued_video_frames_callback=queued_video_frames_callback,
    queued_audio_frames_callback=queued_audio_frames_callback,
    async_processing=True,
)
