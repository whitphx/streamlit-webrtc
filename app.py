import logging
import logging.handlers
import urllib.request
import os
from pathlib import Path
from typing import Literal

import cv2
import numpy as np
import streamlit as st
from av import VideoFrame
from aiortc.contrib.media import MediaPlayer
from streamlit_webrtc import (
    webrtc_streamer,
    WebRtcMode,
    ClientSettings,
    VideoTransformerBase,
)

logging.basicConfig(level=logging.DEBUG)

ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
ch.setFormatter(formatter)
logging.getLogger("streamlit_webrtc").addHandler(ch)

HERE = Path(__file__).parent


# This code is based on https://github.com/streamlit/demo-self-driving/blob/230245391f2dda0cb464008195a470751c01770b/streamlit_app.py#L48
def download_file(url, download_to: Path, expected_size=None):
    # Don't download the file twice. (If possible, verify the download using the file length.)
    if download_to.exists() and expected_size is not None:
        if download_to.stat().st_size == expected_size:
            return

    download_to.parent.mkdir(parents=True, exist_ok=True)

    # These are handles to two visual elements to animate.
    weights_warning, progress_bar = None, None
    try:
        weights_warning = st.warning("Downloading %s..." % url)
        progress_bar = st.progress(0)
        with open(download_to, "wb") as output_file:
            with urllib.request.urlopen(url) as response:
                length = int(response.info()["Content-Length"])
                counter = 0.0
                MEGABYTES = 2.0 ** 20.0
                while True:
                    data = response.read(8192)
                    if not data:
                        break
                    counter += len(data)
                    output_file.write(data)

                    # We perform animation by overwriting the elements.
                    weights_warning.warning(
                        "Downloading %s... (%6.2f/%6.2f MB)"
                        % (url, counter / MEGABYTES, length / MEGABYTES)
                    )
                    progress_bar.progress(min(counter / length, 1.0))
    # Finally, we remove these visual elements by calling .empty().
    finally:
        if weights_warning is not None:
            weights_warning.empty()
        if progress_bar is not None:
            progress_bar.empty()


st.header("WebRTC component")

client_settings = ClientSettings(
    rtc_configuration={"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]},
    media_stream_constraints={"video": True, "audio": True},
)

loopback_page = "Loopback (sendrecv)"
transform_page = "Transform video stream (sendrecv)"
transform_with_nn_page = "Transform video stream with NN model (sendrecv)"
serverside_play_page = (
    "Consume a video on server-side and play it on client-side (recvonly)"
)
app_mode = st.sidebar.selectbox(
    "Choose the app mode",
    [
        loopback_page,
        transform_page,
        transform_with_nn_page,
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

    class OpenCVVideoTransformer(VideoTransformerBase):
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
                img = cv2.cvtColor(cv2.Canny(img, 100, 200), cv2.COLOR_GRAY2BGR)
            elif self.type == "rotate":
                # rotate image
                rows, cols, _ = img.shape
                M = cv2.getRotationMatrix2D((cols / 2, rows / 2), frame.time * 45, 1)
                img = cv2.warpAffine(img, M, (cols, rows))

            return img

    webrtc_ctx = webrtc_streamer(
        key=app_mode,
        mode=WebRtcMode.SENDRECV,
        client_settings=client_settings,
        video_transformer_class=OpenCVVideoTransformer,
        async_transform=True,
    )

    transform_type = st.radio(
        "Select transform type", ("noop", "cartoon", "edges", "rotate")
    )
    if webrtc_ctx.video_transformer:
        webrtc_ctx.video_transformer.type = transform_type

elif app_mode == transform_with_nn_page:

    # This detection model and code are based on https://github.com/robmarkcole/object-detection-app

    CLASSES = [
        "background",
        "aeroplane",
        "bicycle",
        "bird",
        "boat",
        "bottle",
        "bus",
        "car",
        "cat",
        "chair",
        "cow",
        "diningtable",
        "dog",
        "horse",
        "motorbike",
        "person",
        "pottedplant",
        "sheep",
        "sofa",
        "train",
        "tvmonitor",
    ]
    COLORS = np.random.uniform(0, 255, size=(len(CLASSES), 3))

    MODEL_URL = "https://github.com/robmarkcole/object-detection-app/raw/master/model/MobileNetSSD_deploy.caffemodel"
    MODEL_LOCAL_PATH = HERE / "./models/MobileNetSSD_deploy.caffemodel"
    PROTOTXT_URL = "https://github.com/robmarkcole/object-detection-app/raw/master/model/MobileNetSSD_deploy.prototxt.txt"
    PROTOTXT_LOCAL_PATH = HERE / "./models/MobileNetSSD_deploy.prototxt.txt"

    download_file(MODEL_URL, MODEL_LOCAL_PATH, expected_size=23147564)
    download_file(PROTOTXT_URL, PROTOTXT_LOCAL_PATH, expected_size=29353)

    DEFAULT_CONFIDENCE_THRESHOLD = 0.5

    class NNVideoTransformer(VideoTransformerBase):
        confidence_threshold: float

        def __init__(self) -> None:
            self._net = cv2.dnn.readNetFromCaffe(
                str(PROTOTXT_LOCAL_PATH), str(MODEL_LOCAL_PATH)
            )
            self.confidence_threshold = 0.8

        def _annotate_image(self, image, detections):
            # loop over the detections
            (h, w) = image.shape[:2]
            labels = []
            for i in np.arange(0, detections.shape[2]):
                confidence = detections[0, 0, i, 2]

                if confidence > self.confidence_threshold:
                    # extract the index of the class label from the `detections`,
                    # then compute the (x, y)-coordinates of the bounding box for
                    # the object
                    idx = int(detections[0, 0, i, 1])
                    box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                    (startX, startY, endX, endY) = box.astype("int")

                    # display the prediction
                    label = f"{CLASSES[idx]}: {round(confidence * 100, 2)}%"
                    labels.append(label)
                    cv2.rectangle(image, (startX, startY), (endX, endY), COLORS[idx], 2)
                    y = startY - 15 if startY - 15 > 15 else startY + 15
                    cv2.putText(
                        image,
                        label,
                        (startX, y),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        COLORS[idx],
                        2,
                    )
            return image, labels

        def transform(self, frame: VideoFrame) -> np.ndarray:
            image = frame.to_ndarray(format="bgr24")
            blob = cv2.dnn.blobFromImage(
                cv2.resize(image, (300, 300)), 0.007843, (300, 300), 127.5
            )
            self._net.setInput(blob)
            detections = self._net.forward()
            annotated_image, labels = self._annotate_image(image, detections)
            # TODO: Show labels

            return annotated_image

    webrtc_ctx = webrtc_streamer(
        key=app_mode,
        mode=WebRtcMode.SENDRECV,
        client_settings=client_settings,
        video_transformer_class=NNVideoTransformer,
        async_transform=True,
    )

    confidence_threshold = st.slider(
        "Confidence threshold", 0.0, 1.0, DEFAULT_CONFIDENCE_THRESHOLD, 0.05
    )
    if webrtc_ctx.video_transformer:
        webrtc_ctx.video_transformer.confidence_threshold = confidence_threshold


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
