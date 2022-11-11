import logging

import streamlit as st

logger = logging.getLogger()

st.title("streamlit-webrtc demo!")
st.info(
    """👈 Select the demo
"""
)


if __name__ == "__main__":
    import os

    DEBUG = os.environ.get("DEBUG", "false").lower() not in ["false", "no", "0"]

    logging.basicConfig(
        format="[%(asctime)s] %(levelname)7s from %(name)s in %(pathname)s:%(lineno)d: "
        "%(message)s",
        level=logging.DEBUG if DEBUG else logging.INFO,
        force=True,
    )

    fsevents_logger = logging.getLogger("fsevents")
    fsevents_logger.setLevel(logging.WARNING)

    aiortc_logger = logging.getLogger("aiortc")
    aiortc_logger.setLevel(logging.INFO)

    aioice_logger = logging.getLogger("aioice")
    aioice_logger.setLevel(logging.INFO)
