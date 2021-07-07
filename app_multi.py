import logging
import math
import queue
from pathlib import Path
from typing import List, NamedTuple

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
from streamlit_webrtc.factory import create_mux_track, create_process_track
from streamlit_webrtc.mux import MuxerBase

logger = logging.getLogger(__name__)

HERE = Path(__file__).parent


class MultiWindowMuxer(MuxerBase):
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

            window_offset_x = int((grid_w - window_w) / 2)
            window_offset_y = int((grid_h - window_h) / 2)

            window_x = grid_x + window_offset_x
            window_y = grid_y + window_offset_y

            buffer[
                window_y : window_y + window_h, window_x : window_x + window_w, :
            ] = cv2.resize(img, (window_w, window_h))

            na_frame = frame

        if na_frame is None:
            return None

        new_frame = av.VideoFrame.from_ndarray(buffer, format="bgr24")

        new_frame.pts = na_frame.pts
        new_frame.time_base = na_frame.time_base

        return new_frame


MODEL_URL = "https://github.com/robmarkcole/object-detection-app/raw/master/model/MobileNetSSD_deploy.caffemodel"  # noqa: E501
MODEL_LOCAL_PATH = HERE / "./models/MobileNetSSD_deploy.caffemodel"
PROTOTXT_URL = "https://github.com/robmarkcole/object-detection-app/raw/master/model/MobileNetSSD_deploy.prototxt.txt"  # noqa: E501
PROTOTXT_LOCAL_PATH = HERE / "./models/MobileNetSSD_deploy.prototxt.txt"

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

# download_file(MODEL_URL, MODEL_LOCAL_PATH, expected_size=23147564)
# download_file(PROTOTXT_URL, PROTOTXT_LOCAL_PATH, expected_size=29353)

DEFAULT_CONFIDENCE_THRESHOLD = 0.5


class Detection(NamedTuple):
    name: str
    prob: float


class MobileNetSSDVideoProcessor(VideoProcessorBase):
    confidence_threshold: float
    result_queue: "queue.Queue[List[Detection]]"

    def __init__(self) -> None:
        self._net = cv2.dnn.readNetFromCaffe(
            str(PROTOTXT_LOCAL_PATH), str(MODEL_LOCAL_PATH)
        )
        self.confidence_threshold = DEFAULT_CONFIDENCE_THRESHOLD
        self.result_queue = queue.Queue()

    def _annotate_image(self, image, detections):
        # loop over the detections
        (h, w) = image.shape[:2]
        result: List[Detection] = []
        for i in np.arange(0, detections.shape[2]):
            confidence = detections[0, 0, i, 2]

            if confidence > self.confidence_threshold:
                # extract the index of the class label from the `detections`,
                # then compute the (x, y)-coordinates of the bounding box for
                # the object
                idx = int(detections[0, 0, i, 1])
                box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                (startX, startY, endX, endY) = box.astype("int")

                name = CLASSES[idx]
                result.append(Detection(name=name, prob=float(confidence)))

                # display the prediction
                label = f"{name}: {round(confidence * 100, 2)}%"
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
        return image, result

    def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
        image = frame.to_ndarray(format="bgr24")
        blob = cv2.dnn.blobFromImage(
            cv2.resize(image, (300, 300)), 0.007843, (300, 300), 127.5
        )
        self._net.setInput(blob)
        detections = self._net.forward()
        annotated_image, result = self._annotate_image(image, detections)

        # NOTE: This `recv` method is called in another thread,
        # so it must be thread-safe.
        self.result_queue.put(result)

        return av.VideoFrame.from_ndarray(annotated_image, format="bgr24")


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

    mux_track = create_mux_track(
        kind="video", muxer_factory=MultiWindowMuxer, key="mux"
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
        source_video_track=mux_track,
    )

    if mux_ctx.source_video_track:
        if input1_ctx.output_video_track:
            video_process_track = create_process_track(
                input_track=input1_ctx.output_video_track,
                processor_factory=MobileNetSSDVideoProcessor,
            )
            mux_ctx.source_video_track.add_input_track(video_process_track)
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
    st_webrtc_logger.setLevel(logging.DEBUG if DEBUG else logging.INFO)

    aioice_logger = logging.getLogger("aioice")
    aioice_logger.setLevel(logging.WARNING)

    fsevents_logger = logging.getLogger("fsevents")
    fsevents_logger.setLevel(logging.WARNING)

    # app()
    n_to_1()
