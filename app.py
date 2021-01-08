import logging
import logging.handlers
from typing import Literal

import cv2
import streamlit as st
from av import VideoFrame
from aiortc.contrib.media import MediaPlayer
from streamlit_webrtc import webrtc_streamer, WebRtcMode, ClientSettings, VideoTransformerBase

logging.basicConfig(level=logging.DEBUG)

ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logging.getLogger("streamlit_webrtc").addHandler(ch)

st.header("WebRTC component")

client_settings = ClientSettings(
    rtc_configuration={
        "iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]
    },
    media_stream_constraints={"video": True, "audio": True},
)

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
    webrtc_streamer(
        key=app_mode,
        mode=WebRtcMode.SENDRECV,
        client_settings=client_settings,
        video_transformer_class=None,  # NoOp
    )
elif app_mode == transform_page:

    class VideoEdgeTransformer(VideoTransformerBase):
        type: Literal["noop", "cartoon", "edges", "rotate"]

        def __init__(self) -> None:
            self.type = "noop"

        def transform(self, frame: VideoFrame) -> VideoFrame:
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
                img = cv2.cvtColor(
                    cv2.Canny(img, 100, 200), cv2.COLOR_GRAY2BGR)
            elif self.type == "rotate":
                # rotate image
                rows, cols, _ = img.shape
                M = cv2.getRotationMatrix2D(
                    (cols / 2, rows / 2), frame.time * 45, 1
                )
                img = cv2.warpAffine(img, M, (cols, rows))

            return img

    webrtc_ctx = webrtc_streamer(
        key=app_mode,
        mode=WebRtcMode.SENDRECV,
        client_settings=client_settings,
        video_transformer_class=VideoEdgeTransformer,
        async_transform=True,
    )

    transform_type = st.radio(
        "Select transform type", ("noop", "cartoon", "edges", "rotate")
    )
    if webrtc_ctx.video_transformer:
        webrtc_ctx.video_transformer.type = transform_type
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

    webrtc_streamer(
        key=app_mode,
        mode=WebRtcMode.RECVONLY,
        client_settings=client_settings,
        player_factory=create_player,
    )
