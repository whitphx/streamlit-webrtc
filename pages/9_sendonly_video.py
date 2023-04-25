"""A sample to use WebRTC in sendonly mode to transfer frames
from the browser to the server and to render frames via `st.image`."""

import logging
import queue

import streamlit as st
from streamlit_webrtc import WebRtcMode, webrtc_streamer

from sample_utils.turn import get_ice_servers

logger = logging.getLogger(__name__)


webrtc_ctx = webrtc_streamer(
    key="video-sendonly",
    mode=WebRtcMode.SENDONLY,
    rtc_configuration={"iceServers": get_ice_servers()},
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
