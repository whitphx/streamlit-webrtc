import asyncio
import enum
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
                )
                webrtc_worker.process_offer(sdp_offer["sdp"], sdp_offer["type"])
                set_webrtc_worker(key, webrtc_worker)
                st.experimental_rerun()  # Rerun to send the SDP answer to frontend

    return component_value


# Add some test code to play with the component while it's in development.
# During development, we can run this just as we would any other Streamlit
# app: `$ streamlit run my_component/__init__.py`
if not _RELEASE:
    import streamlit as st
    import cv2
    from av import VideoFrame

    logging.basicConfig()

    st.header("WebRTC component")

    loopback_page = "Loopback (sendrecv)"
    transform_page = "Transform video stream (sendrecv)"
    serverside_play_page = (
        "Consume a video on server-side and play it on client-side (recvonly)"
    )
    app_mode = st.sidebar.selectbox(
        "Choose the app mode",
        [
            loopback_page,
            transform_page,
            serverside_play_page,
        ],
    )
    if app_mode == loopback_page:
        my_component(
            key=app_mode,
            mode=WebRtcMode.SENDRECV,
            video_transformer_class=None,  # NoOp
        )
    elif app_mode == transform_page:

        class TransformType(enum.Enum):
            NOOP = enum.auto()
            CARTOON = enum.auto()
            EDGES = enum.auto()
            ROTATE = enum.auto()

        class VideoEdgeTransformer(VideoTransformerBase):
            type: TransformType

            def __init__(self) -> None:
                self.type = TransformType.EDGE

            def transform(self, frame: VideoFrame) -> VideoFrame:
                if self.type == TransformType.NOOP:
                    return frame

                img = frame.to_ndarray(format="bgr24")

                if self.type == TransformType.CARTOON:
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
                elif self.type == TransformType.EDGES:
                    # perform edge detection
                    img = cv2.cvtColor(cv2.Canny(img, 100, 200), cv2.COLOR_GRAY2BGR)
                elif self.type == TransformType.ROTATE:
                    # rotate image
                    rows, cols, _ = img.shape
                    M = cv2.getRotationMatrix2D(
                        (cols / 2, rows / 2), frame.time * 45, 1
                    )
                    img = cv2.warpAffine(img, M, (cols, rows))

                # rebuild a VideoFrame, preserving timing information
                new_frame = VideoFrame.from_ndarray(img, format="bgr24")
                new_frame.pts = frame.pts
                new_frame.time_base = frame.time_base
                return new_frame

        my_component(
            key=app_mode,
            mode=WebRtcMode.SENDRECV,
            video_transformer_class=VideoEdgeTransformer,
        )
    elif app_mode == serverside_play_page:

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
            mode=WebRtcMode.RECVONLY,
            player_factory=create_player,
        )
