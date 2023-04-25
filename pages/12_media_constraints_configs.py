"""A sample to configure MediaStreamConstraints object"""

import streamlit as st
from streamlit_webrtc import WebRtcMode, webrtc_streamer

from sample_utils.turn import get_ice_servers

frame_rate = 5
webrtc_streamer(
    key="media-constraints",
    mode=WebRtcMode.SENDRECV,
    rtc_configuration={"iceServers": get_ice_servers()},
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
