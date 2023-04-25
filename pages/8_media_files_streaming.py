"""Media streamings"""
import logging
from pathlib import Path
from typing import Dict, Optional, cast

import av
import cv2
import streamlit as st
from aiortc.contrib.media import MediaPlayer
from streamlit_webrtc import WebRtcMode, WebRtcStreamerContext, webrtc_streamer

from sample_utils.download import download_file
from sample_utils.turn import get_ice_servers

HERE = Path(__file__).parent
ROOT = HERE.parent

logger = logging.getLogger(__name__)


MEDIAFILES: Dict[str, Dict] = {
    "big_buck_bunny_720p_2mb.mp4 (local)": {
        "url": "https://sample-videos.com/video123/mp4/720/big_buck_bunny_720p_2mb.mp4",  # noqa: E501
        "local_file_path": ROOT / "data/big_buck_bunny_720p_2mb.mp4",
        "type": "video",
    },
    "big_buck_bunny_720p_10mb.mp4 (local)": {
        "url": "https://sample-videos.com/video123/mp4/720/big_buck_bunny_720p_10mb.mp4",  # noqa: E501
        "local_file_path": ROOT / "data/big_buck_bunny_720p_10mb.mp4",
        "type": "video",
    },
    "file_example_MP3_700KB.mp3 (local)": {
        "url": "https://file-examples-com.github.io/uploads/2017/11/file_example_MP3_700KB.mp3",  # noqa: E501
        "local_file_path": ROOT / "data/file_example_MP3_700KB.mp3",
        "type": "audio",
    },
    "file_example_MP3_5MG.mp3 (local)": {
        "url": "https://file-examples-com.github.io/uploads/2017/11/file_example_MP3_5MG.mp3",  # noqa: E501
        "local_file_path": ROOT / "data/file_example_MP3_5MG.mp3",
        "type": "audio",
    },
    "rtsp://wowzaec2demo.streamlock.net/vod/mp4:BigBuckBunny_115k.mov": {
        "url": "rtsp://wowzaec2demo.streamlock.net/vod/mp4:BigBuckBunny_115k.mov",
        "type": "video",
    },
}
media_file_label = st.radio("Select a media source to stream", tuple(MEDIAFILES.keys()))
media_file_info = MEDIAFILES[cast(str, media_file_label)]
if "local_file_path" in media_file_info:
    download_file(media_file_info["url"], media_file_info["local_file_path"])


def create_player():
    if "local_file_path" in media_file_info:
        return MediaPlayer(str(media_file_info["local_file_path"]))
    else:
        return MediaPlayer(media_file_info["url"])

    # NOTE: To stream the video from webcam, use the code below.
    # return MediaPlayer(
    #     "1:none",
    #     format="avfoundation",
    #     options={"framerate": "30", "video_size": "1280x720"},
    # )


key = f"media-streaming-{media_file_label}"
ctx: Optional[WebRtcStreamerContext] = st.session_state.get(key)
if media_file_info["type"] == "video" and ctx and ctx.state.playing:
    _type = st.radio("Select transform type", ("noop", "cartoon", "edges", "rotate"))
else:
    _type = "noop"


def video_frame_callback(frame: av.VideoFrame) -> av.VideoFrame:
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


webrtc_streamer(
    key=key,
    mode=WebRtcMode.RECVONLY,
    rtc_configuration={"iceServers": get_ice_servers()},
    media_stream_constraints={
        "video": media_file_info["type"] == "video",
        "audio": media_file_info["type"] == "audio",
    },
    player_factory=create_player,
    video_frame_callback=video_frame_callback,
)

st.markdown(
    "The video filter in this demo is based on "
    "https://github.com/aiortc/aiortc/blob/2362e6d1f0c730a0f8c387bbea76546775ad2fe8/examples/server/server.py#L34. "  # noqa: E501
    "Many thanks to the project."
)
