import asyncio
import os
import json
import logging
from typing import Dict, Hashable, Union, Optional
import streamlit.components.v1 as components
from aiortc.contrib.media import MediaPlayer

from webrtc import (
    WebRtcWorker,
    MediaPlayerFactory,
    WebRtcMode,
    VideoTransformerBase,
    VideoGeneratorBase,
)
import SessionState


_RELEASE = False

if not _RELEASE:
    _component_func = components.declare_component(
        "my_component",
        url="http://localhost:3001",
    )
else:
    parent_dir = os.path.dirname(os.path.abspath(__file__))
    build_dir = os.path.join(parent_dir, "frontend/build")
    _component_func = components.declare_component("my_component", path=build_dir)


session_state = SessionState.get(webrtc_workers={})


def get_webrtc_worker(key: Hashable) -> Union[WebRtcWorker, None]:
    return session_state.webrtc_workers.get(key)


def set_webrtc_worker(key: Hashable, webrtc_worker: WebRtcWorker) -> None:
    session_state.webrtc_workers[key] = webrtc_worker


def unset_webrtc_worker(key: Hashable) -> None:
    del session_state.webrtc_workers[key]


def my_component(
    key: str,
    mode: WebRtcMode = WebRtcMode.SENDRECV,
    player_factory: Optional[MediaPlayerFactory] = None,
    video_transformer_class: Optional[VideoTransformerBase] = None,
    video_generator_class: Optional[VideoGeneratorBase] = None,
):
    webrtc_worker = get_webrtc_worker(key)

    sdp_answer_json = None
    if webrtc_worker:
        sdp_answer_json = json.dumps(
            {
                "sdp": webrtc_worker.pc.localDescription.sdp,
                "type": webrtc_worker.pc.localDescription.type,
            }
        )

    component_value: Union[Dict, None] = _component_func(
        key=key, sdp_answer_json=sdp_answer_json, mode=mode.name
    )

    if component_value:
        playing = component_value.get("playing", False)
        sdp_offer = component_value.get("sdpOffer")

        if webrtc_worker:
            if not playing:
                webrtc_worker.stop()
                unset_webrtc_worker(key)
        else:
            if sdp_offer:
                webrtc_worker = WebRtcWorker(
                    mode=mode,
                    player_factory=player_factory,
                    video_transformer_class=video_transformer_class,
                    video_generator_class=video_generator_class,
                )
                webrtc_worker.process_offer(sdp_offer["sdp"], sdp_offer["type"])
                set_webrtc_worker(key, webrtc_worker)
                st.experimental_rerun()  # Rerun to send the SDP answer to frontend

    return component_value


# Add some test code to play with the component while it's in development.
# During development, we can run this just as we would any other Streamlit
# app: `$ streamlit run my_component/__init__.py`
if not _RELEASE:
    import fractions
    import streamlit as st
    import cv2
    import numpy as np

    logging.basicConfig()

    st.header("WebRTC component")

    mode = WebRtcMode.SENDRECV
    player_factory = None
    video_transformer_class = None
    video_generator_class = None

    loopback_page = "Loopback (sendrecv)"
    transform_page = "Transform video stream (sendrecv)"
    generate_page = "Generate video stream (recvonly)"
    serverside_play_page = (
        "Consume a video on server-side and play it on client-side (recvonly)"
    )
    app_mode = st.sidebar.selectbox(
        "Choose the app mode",
        [loopback_page, transform_page, generate_page, serverside_play_page],
    )
    if app_mode == loopback_page:
        mode = WebRtcMode.SENDRECV
    elif app_mode == transform_page:
        mode = WebRtcMode.SENDRECV

        class VideoEdgeTransformer(VideoTransformerBase):
            def transform(self, frame_bgr24: np.ndarray) -> np.ndarray:
                return cv2.cvtColor(
                    cv2.Canny(frame_bgr24, 100, 200), cv2.COLOR_GRAY2BGR
                )

        video_transformer_class = VideoEdgeTransformer
    elif app_mode == generate_page:
        # mode = WebRtcMode.RECVONLY  # TODO: It should be RECVONLY

        class RotationImageVideoGenerator(VideoGeneratorBase):
            def __init__(self) -> None:
                self.img = cv2.imread("./photo.jpg", cv2.IMREAD_COLOR)

            def generate(self, pts: int, time_base: fractions.Fraction) -> np.ndarray:
                rows, cols, _ = self.img.shape
                M = cv2.getRotationMatrix2D(
                    (cols / 2, rows / 2), int(pts * time_base * 45), 1
                )
                return cv2.warpAffine(self.img, M, (cols, rows))

        video_generator_class = RotationImageVideoGenerator

    elif app_mode == serverside_play_page:
        # mode = WebRtcMode.RECVONLY  # TODO: It should be RECVONLY

        def create_player():
            # TODO: Be configurable
            return MediaPlayer("./sample-mp4-file.mp4")
            # return MediaPlayer("./demo-instruct.wav")
            # return MediaPlayer(
            #     "1:none",
            #     format="avfoundation",
            #     options={"framerate": "30", "video_size": "1280x720"},
            # )

        player_factory = create_player

    my_component(
        key=app_mode,
        player_factory=player_factory,
        mode=mode,
        video_transformer_class=video_transformer_class,
        video_generator_class=video_generator_class,
    )
