"""A sample to verify custom component interactivity during a slow rerun."""

import time
from datetime import datetime

import streamlit as st

from streamlit_webrtc import WebRtcMode, webrtc_streamer

st.title("Disabled during slow rerun")

delay_seconds = st.slider("Slow action duration", min_value=1, max_value=15, value=8)

st.write(
    "Click the slow action button, then try clicking the WebRTC Start button while "
    "Streamlit dims the previous UI."
)

if "slow_action_count" not in st.session_state:
    st.session_state.slow_action_count = 0

if "native_click_count" not in st.session_state:
    st.session_state.native_click_count = 0

if st.button("Trigger slow rerun"):
    st.session_state.slow_action_count += 1
    started_at = datetime.now().strftime("%H:%M:%S")
    with st.spinner(f"Sleeping for {delay_seconds} seconds. Started at {started_at}."):
        time.sleep(delay_seconds)

st.write(f"Slow reruns triggered: {st.session_state.slow_action_count}")
st.write(f"Last completed render: {datetime.now().strftime('%H:%M:%S')}")

webrtc_streamer(
    key="disabled-during-run",
    mode=WebRtcMode.SENDRECV,
    media_stream_constraints={"video": True, "audio": False},
)

if st.button("Native control button"):
    st.session_state.native_click_count += 1

st.write(f"Native control clicks: {st.session_state.native_click_count}")
