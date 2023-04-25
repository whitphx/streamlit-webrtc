import math
from typing import List

try:
    from typing import Literal, cast
except ImportError:
    from typing_extensions import Literal  # type: ignore

import av
import cv2
import numpy as np
import streamlit as st
from streamlit_webrtc import (
    WebRtcMode,
    create_mix_track,
    create_process_track,
    webrtc_streamer,
)

from sample_utils.turn import get_ice_servers

st.markdown(
    """
Mix multiple inputs with different video filters into one stream.
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


def mixer_callback(frames: List[av.VideoFrame]) -> av.VideoFrame:
    buf_w = 640
    buf_h = 480
    buffer = np.zeros((buf_h, buf_w, 3), dtype=np.uint8)

    n_inputs = len(frames)

    n_cols = math.ceil(math.sqrt(n_inputs))
    n_rows = math.ceil(n_inputs / n_cols)
    grid_w = buf_w // n_cols
    grid_h = buf_h // n_rows

    for i in range(n_inputs):
        frame = frames[i]
        if frame is None:
            continue

        grid_x = (i % n_cols) * grid_w
        grid_y = (i // n_cols) * grid_h

        img = frame.to_ndarray(format="bgr24")
        src_h, src_w = img.shape[0:2]

        aspect_ratio = src_w / src_h

        window_w = min(grid_w, int(grid_h * aspect_ratio))
        window_h = min(grid_h, int(window_w / aspect_ratio))

        window_offset_x = (grid_w - window_w) // 2
        window_offset_y = (grid_h - window_h) // 2

        window_x0 = grid_x + window_offset_x
        window_y0 = grid_y + window_offset_y
        window_x1 = window_x0 + window_w
        window_y1 = window_y0 + window_h

        buffer[window_y0:window_y1, window_x0:window_x1, :] = cv2.resize(
            img, (window_w, window_h)
        )

    new_frame = av.VideoFrame.from_ndarray(buffer, format="bgr24")

    return new_frame


COMMON_RTC_CONFIG = {"iceServers": get_ice_servers()}

st.header("Input 1")
input1_ctx = webrtc_streamer(
    key="input1_ctx",
    mode=WebRtcMode.SENDRECV,
    rtc_configuration=COMMON_RTC_CONFIG,
    media_stream_constraints={"video": True, "audio": False},
)
filter1_type = st.radio(
    "Select transform type",
    ("noop", "cartoon", "edges", "rotate"),
    key="mix-filter1-type",
)
callback = make_video_frame_callback(cast(VideoFilterType, filter1_type))
input1_video_process_track = None
if input1_ctx.output_video_track:
    input1_video_process_track = create_process_track(
        input_track=input1_ctx.output_video_track,
        frame_callback=callback,
    )

st.header("Input 2")
input2_ctx = webrtc_streamer(
    key="input2_ctx",
    mode=WebRtcMode.SENDRECV,
    rtc_configuration=COMMON_RTC_CONFIG,
    media_stream_constraints={"video": True, "audio": False},
)
filter2_type = st.radio(
    "Select transform type",
    ("noop", "cartoon", "edges", "rotate"),
    key="mix-filter2-type",
)
callback = make_video_frame_callback(cast(VideoFilterType, filter2_type))
input2_video_process_track = None
if input2_ctx.output_video_track:
    input2_video_process_track = create_process_track(
        input_track=input2_ctx.output_video_track, frame_callback=callback
    )

st.header("Input 3 (no filter)")
input3_ctx = webrtc_streamer(
    key="input3_ctx",
    mode=WebRtcMode.SENDRECV,
    rtc_configuration=COMMON_RTC_CONFIG,
    media_stream_constraints={"video": True, "audio": False},
)

st.header("Mixed output")
mix_track = create_mix_track(kind="video", mixer_callback=mixer_callback, key="mix")
mix_ctx = webrtc_streamer(
    key="mix",
    mode=WebRtcMode.RECVONLY,
    rtc_configuration=COMMON_RTC_CONFIG,
    source_video_track=mix_track,
    desired_playing_state=input1_ctx.state.playing
    or input2_ctx.state.playing
    or input3_ctx.state.playing,
)

if mix_ctx.source_video_track and input1_video_process_track:
    mix_ctx.source_video_track.add_input_track(input1_video_process_track)
if mix_ctx.source_video_track and input2_video_process_track:
    mix_ctx.source_video_track.add_input_track(input2_video_process_track)
if mix_ctx.source_video_track and input3_ctx.output_video_track:
    # Input3 is sourced without any filter.
    mix_ctx.source_video_track.add_input_track(input3_ctx.output_video_track)
