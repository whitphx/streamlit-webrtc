"""A sample of controlling the playing state from Python."""

import streamlit as st
from streamlit_webrtc import WebRtcMode, webrtc_streamer

from sample_utils.turn import get_ice_servers

playing = st.checkbox("Playing", value=True)

webrtc_streamer(
    key="programatic_control",
    desired_playing_state=playing,
    mode=WebRtcMode.SENDRECV,
    rtc_configuration={"iceServers": get_ice_servers()},
)
