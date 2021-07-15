import logging
import math
from collections import OrderedDict
from typing import List

try:
    from typing import Literal
except ImportError:
    from typing_extensions import Literal  # type: ignore

import av
import cv2
import numpy as np
import streamlit as st
from streamlit_server_state import server_state, server_state_lock

from streamlit_webrtc import (
    ClientSettings,
    VideoProcessorBase,
    WebRtcMode,
    webrtc_streamer,
)
from streamlit_webrtc.factory import create_mux_track, create_process_track
from streamlit_webrtc.mix import MixerBase

logger = logging.getLogger(__name__)


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


class MultiWindowMixer(MixerBase):
    def on_update(self, frames: List[av.VideoFrame]) -> av.VideoFrame:
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


def main():
    with server_state_lock["webrtc_contexts"]:
        if "webrtc_contexts" not in server_state:
            server_state["webrtc_contexts"] = OrderedDict()

    with server_state_lock["mux_track"]:
        if "mux_track" not in server_state:
            server_state["mux_track"] = create_mux_track(
                kind="video", mixer_factory=MultiWindowMixer, key="mux"
            )

    mux_track = server_state["mux_track"]

    self_ctx = webrtc_streamer(
        key="self",
        mode=WebRtcMode.SENDRECV,
        client_settings=ClientSettings(
            rtc_configuration={
                "iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]
            },
            media_stream_constraints={"video": True, "audio": True},
        ),
        source_video_track=mux_track,
        sendback_audio=False,
    )

    self_process_track = None
    if self_ctx.input_video_track:
        self_process_track = create_process_track(
            input_track=self_ctx.input_video_track,
            processor_factory=OpenCVVideoProcessor,
        )
        mux_track.add_input_track(self_process_track)

        self_process_track.processor.type = st.radio(
            "Select transform type",
            ("noop", "cartoon", "edges", "rotate"),
            key="filter1-type",
        )

    with server_state_lock["webrtc_contexts"]:
        webrtc_contexts: OrderedDict = server_state["webrtc_contexts"]
        self_is_playing = self_ctx.state.playing and self_process_track
        if self_is_playing and self_ctx not in webrtc_contexts:
            webrtc_contexts[self_ctx] = self_process_track
            server_state["webrtc_contexts"] = webrtc_contexts
        elif not self_is_playing and self_ctx in webrtc_contexts:
            del webrtc_contexts[self_ctx]
            server_state["webrtc_contexts"] = webrtc_contexts

    for ctx, track in webrtc_contexts.items():
        if ctx == self_ctx or not ctx.state.playing:
            continue
        # Video streams are handled in MCU manner
        mux_track.add_input_track(track)
        # Audio streams are transferred in SFU manner
        # TODO: Create MCU to mix audio streams
        webrtc_streamer(
            key=f"sound-{id(ctx)}",
            mode=WebRtcMode.RECVONLY,
            client_settings=ClientSettings(
                rtc_configuration={
                    "iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]
                },
                media_stream_constraints={"video": False, "audio": True},
            ),
            source_audio_track=ctx.input_audio_track,
            desired_playing_state=True,
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
    st_webrtc_logger.setLevel(logging.DEBUG if DEBUG else logging.INFO)

    aioice_logger = logging.getLogger("aioice")
    aioice_logger.setLevel(logging.WARNING)

    fsevents_logger = logging.getLogger("fsevents")
    fsevents_logger.setLevel(logging.WARNING)

    main()
