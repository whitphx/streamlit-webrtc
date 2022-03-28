import logging

import streamlit as st
from streamlit_webrtc.coturn.server import start_coturn

logging.basicConfig(
    format="[%(asctime)s] %(levelname)7s from %(name)s in %(pathname)s:%(lineno)d: "
    "%(message)s",
    force=True,
)

# logger.setLevel(level=logging.DEBUG if DEBUG else logging.INFO)

st_webrtc_logger = logging.getLogger("streamlit_webrtc")
st_webrtc_logger.setLevel(logging.DEBUG)

st.button("Rerun")

start_coturn(listening_port=3478, tls_listening_port=5349, fingerprint=True, lt_cred_mech=True, server_name="localhost", realm="localhost", user="hoge:pass")
