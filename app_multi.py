from typing import List
import logging

try:
    from typing import Literal
except ImportError:
    from typing_extensions import Literal  # type: ignore

import av
import cv2
import numpy as np
import streamlit as st

from streamlit_webrtc import (
    ClientSettings,
    VideoProcessorBase,
    WebRtcMode,
    webrtc_streamer,
)
from streamlit_webrtc.mux import MediaStreamTrackMuxer

logger = logging.getLogger(__name__)


class SliceMuxer(MediaStreamTrackMuxer):
    kind = "video"

    _colors = [
        (255, 0, 0),
        (0, 255, 0),
        (0, 0, 255),
    ]

    def on_update(self, frames: List[av.VideoFrame]) -> av.VideoFrame:
        buf_w = 640
        buf_h = 480
        buffer = np.zeros((buf_h, buf_w, 3), dtype=np.uint8)

        n_split = len(frames)
        na_frame = None  # TODO: Provide the updated frame
        for i in range(n_split):
            frame = frames[i]
            if frame is None:
                continue

            img = frame.to_ndarray(format="bgr24")
            h, w = img.shape[0:2]
            src_fragment_x1 = int(i * w / n_split)
            src_fragment_x2 = int((i + 1) * w / n_split)
            src_fragment = img[:, src_fragment_x1:src_fragment_x2, :]

            # Alpha blending
            color = self._colors[i % len(self._colors)]
            color_buf = np.tile(
                np.reshape(color, (1, 1, 3)).astype(np.uint8),
                (src_fragment.shape[0], src_fragment.shape[1], 1),
            )
            src_fragment = cv2.addWeighted(src_fragment, 0.5, color_buf, 0.5, 0)

            dst_fragment_x1 = int(i * buf_w / n_split)
            dst_fragment_x2 = int((i + 1) * buf_w / n_split)
            dst_fragment_w = dst_fragment_x2 - dst_fragment_x1
            buffer[:, dst_fragment_x1:dst_fragment_x2, :] = cv2.resize(
                src_fragment, (dst_fragment_w, buf_h)
            )

            na_frame = frame

        if na_frame is None:
            return None

        new_frame = av.VideoFrame.from_ndarray(buffer, format="bgr24")

        new_frame.pts = na_frame.pts
        new_frame.time_base = na_frame.time_base

        return new_frame


def n_to_1():
    input1_ctx = webrtc_streamer(
        key="input1_ctx",
        mode=WebRtcMode.SENDRECV,
        client_settings=ClientSettings(
            rtc_configuration={
                "iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]
            },
            media_stream_constraints={
                "video": True,
                "audio": True,
            },
        ),
        video_processor_factory=None,  # NoOp
    )

    input2_ctx = webrtc_streamer(
        key="input2_ctx",
        mode=WebRtcMode.SENDRECV,
        client_settings=ClientSettings(
            rtc_configuration={
                "iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]
            },
            media_stream_constraints={
                "video": True,
                "audio": True,
            },
        ),
        video_processor_factory=None,  # NoOp
    )

    mux_ctx = webrtc_streamer(
        key="mux",
        mode=WebRtcMode.RECVONLY,
        client_settings=ClientSettings(
            rtc_configuration={
                "iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]
            },
            media_stream_constraints={
                "video": True,
                "audio": True,
            },
        ),
        source_video_track=SliceMuxer(kind="video"),
    )

    if mux_ctx.source_video_track:
        if input1_ctx.output_video_track:
            mux_ctx.source_video_track.add_input_track(input1_ctx.output_video_track)
        if input2_ctx.output_video_track:
            mux_ctx.source_video_track.add_input_track(input2_ctx.output_video_track)


def app():
    class OpenCVVideoProcessor(VideoProcessorBase):
        type: Literal["noop", "cartoon", "edges", "rotate"]

        def __init__(self) -> None:
            self.type = "noop"

        def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
            img = frame.to_ndarray(format="bgr24")

            if self.type == "noop":
                pass
            elif self.type == "cartoon":
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
            elif self.type == "edges":
                # perform edge detection
                img = cv2.cvtColor(cv2.Canny(img, 100, 200), cv2.COLOR_GRAY2BGR)
            elif self.type == "rotate":
                # rotate image
                rows, cols, _ = img.shape
                M = cv2.getRotationMatrix2D((cols / 2, rows / 2), frame.time * 45, 1)
                img = cv2.warpAffine(img, M, (cols, rows))

            return av.VideoFrame.from_ndarray(img, format="bgr24")

    ctx = webrtc_streamer(
        key="loopback",
        mode=WebRtcMode.SENDRECV,
        client_settings=ClientSettings(
            rtc_configuration={
                "iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]
            },
            media_stream_constraints={
                "video": True,
                "audio": True,
            },
        ),
        video_processor_factory=None,  # NoOp
    )

    filter1_ctx = webrtc_streamer(
        key="filter1",
        mode=WebRtcMode.RECVONLY,
        client_settings=ClientSettings(
            rtc_configuration={
                "iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]
            },
            media_stream_constraints={
                "video": True,
                "audio": True,
            },
        ),
        video_processor_factory=OpenCVVideoProcessor,
        source_video_track=ctx.output_video_track,
        desired_playing_state=ctx.state.playing,
    )

    if filter1_ctx.video_processor:
        filter1_ctx.video_processor.type = st.radio(
            "Select transform type",
            ("noop", "cartoon", "edges", "rotate"),
            key="second-radio",
        )

    filter2_ctx = webrtc_streamer(
        key="filter2",
        mode=WebRtcMode.RECVONLY,
        client_settings=ClientSettings(
            rtc_configuration={
                "iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]
            },
            media_stream_constraints={
                "video": True,
                "audio": True,
            },
        ),
        video_processor_factory=OpenCVVideoProcessor,
        source_video_track=ctx.output_video_track,
        desired_playing_state=ctx.state.playing,
    )
    if filter2_ctx.video_processor:
        filter2_ctx.video_processor.type = st.radio(
            "Select transform type",
            ("noop", "cartoon", "edges", "rotate"),
            key="third-radio",
        )


if __name__ == "__main__":
    import os

    DEBUG = os.environ.get("DEBUG", "false").lower() not in ["false", "no", "0"]

    logging.basicConfig(
        format="[%(asctime)s] %(levelname)7s from %(name)s in %(pathname)s:%(lineno)d: "
        "%(message)s",
        force=True,
    )

    logger.setLevel(level=logging.DEBUG if DEBUG else logging.INFO)

    st_webrtc_logger = logging.getLogger("streamlit_webrtc")
    st_webrtc_logger.setLevel(logging.DEBUG)

    aioice_logger = logging.getLogger("aioice")
    aioice_logger.setLevel(logging.WARNING)

    fsevents_logger = logging.getLogger("fsevents")
    fsevents_logger.setLevel(logging.WARNING)

    # app()
    n_to_1()
