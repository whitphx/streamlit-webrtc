import uuid
from pathlib import Path

import av
import cv2
import streamlit as st
from aiortc.contrib.media import MediaRecorder
from streamlit_webrtc import WebRtcMode, webrtc_streamer

from sample_utils.turn import get_ice_servers


def video_frame_callback(frame: av.VideoFrame) -> av.VideoFrame:
    img = frame.to_ndarray(format="bgr24")

    # perform edge detection
    img = cv2.cvtColor(cv2.Canny(img, 100, 200), cv2.COLOR_GRAY2BGR)

    return av.VideoFrame.from_ndarray(img, format="bgr24")


RECORD_DIR = Path("./records")
RECORD_DIR.mkdir(exist_ok=True)


def app():
    if "prefix" not in st.session_state:
        st.session_state["prefix"] = str(uuid.uuid4())
    prefix = st.session_state["prefix"]
    in_file = RECORD_DIR / f"{prefix}_input.flv"
    out_file = RECORD_DIR / f"{prefix}_output.flv"

    def in_recorder_factory() -> MediaRecorder:
        return MediaRecorder(
            str(in_file), format="flv"
        )  # HLS does not work. See https://github.com/aiortc/aiortc/issues/331

    def out_recorder_factory() -> MediaRecorder:
        return MediaRecorder(str(out_file), format="flv")

    webrtc_streamer(
        key="record",
        mode=WebRtcMode.SENDRECV,
        rtc_configuration={"iceServers": get_ice_servers()},
        media_stream_constraints={
            "video": True,
            "audio": True,
        },
        video_frame_callback=video_frame_callback,
        in_recorder_factory=in_recorder_factory,
        out_recorder_factory=out_recorder_factory,
    )

    if in_file.exists():
        with in_file.open("rb") as f:
            st.download_button(
                "Download the recorded video without video filter", f, "input.flv"
            )
    if out_file.exists():
        with out_file.open("rb") as f:
            st.download_button(
                "Download the recorded video with video filter", f, "output.flv"
            )


if __name__ == "__main__":
    app()
