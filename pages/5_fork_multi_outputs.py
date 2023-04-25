try:
    from typing import Literal
except ImportError:
    from typing_extensions import Literal  # type: ignore

from typing import cast

import av
import cv2
import streamlit as st
from streamlit_webrtc import WebRtcMode, webrtc_streamer

from sample_utils.turn import get_ice_servers

st.markdown(
    """
Fork one input to multiple outputs with different video filters.
"""
)

VideoFilterType = Literal["noop", "cartoon", "edges", "rotate"]


def make_video_frame_callback(_type: VideoFilterType):
    def callback(frame: av.VideoFrame) -> av.VideoFrame:
        img = frame.to_ndarray(format="bgr24")

        if _type == "noop":
            pass
        elif _type == "cartoon":
            # prepare color
            img_color = cv2.pyrDown(cv2.pyrDown(img))
            for _ in range(6):
                img_color = cv2.bilateralFilter(img_color, 9, 9, 7)
            img_color = cv2.pyrUp(cv2.pyrUp(img_color))

            # prepare edges
            img_edges = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
            img_edges = cv2.adaptiveThreshold(
                cv2.medianBlur(img_edges, 7),
                255,
                cv2.ADAPTIVE_THRESH_MEAN_C,
                cv2.THRESH_BINARY,
                9,
                2,
            )
            img_edges = cv2.cvtColor(img_edges, cv2.COLOR_GRAY2RGB)

            # combine color and edges
            img = cv2.bitwise_and(img_color, img_edges)
        elif _type == "edges":
            # perform edge detection
            img = cv2.cvtColor(cv2.Canny(img, 100, 200), cv2.COLOR_GRAY2BGR)
        elif _type == "rotate":
            # rotate image
            rows, cols, _ = img.shape
            M = cv2.getRotationMatrix2D((cols / 2, rows / 2), frame.time * 45, 1)
            img = cv2.warpAffine(img, M, (cols, rows))

        return av.VideoFrame.from_ndarray(img, format="bgr24")

    return callback


COMMON_RTC_CONFIG = {"iceServers": get_ice_servers()}

st.header("Input")
ctx = webrtc_streamer(
    key="loopback",
    mode=WebRtcMode.SENDRECV,
    rtc_configuration=COMMON_RTC_CONFIG,
    media_stream_constraints={"video": True, "audio": False},
)

st.header("Forked output 1")
filter1_type = st.radio(
    "Select transform type",
    ("noop", "cartoon", "edges", "rotate"),
    key="fork-filter1-type",
)
callback = make_video_frame_callback(cast(VideoFilterType, filter1_type))
webrtc_streamer(
    key="filter1",
    mode=WebRtcMode.RECVONLY,
    video_frame_callback=callback,
    source_video_track=ctx.output_video_track,
    desired_playing_state=ctx.state.playing,
    rtc_configuration=COMMON_RTC_CONFIG,
    media_stream_constraints={"video": True, "audio": False},
)

st.header("Forked output 2")
filter2_type = st.radio(
    "Select transform type",
    ("noop", "cartoon", "edges", "rotate"),
    key="fork-filter2-type",
)
callback = make_video_frame_callback(cast(VideoFilterType, filter2_type))
webrtc_streamer(
    key="filter2",
    mode=WebRtcMode.RECVONLY,
    video_frame_callback=callback,
    source_video_track=ctx.output_video_track,
    desired_playing_state=ctx.state.playing,
    rtc_configuration=COMMON_RTC_CONFIG,
    media_stream_constraints={"video": True, "audio": False},
)
