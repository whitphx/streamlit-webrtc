"""Detection overlay drawn in the browser from data channel messages.

The server detects moving regions in the camera stream and sends their boxes
over a data channel; `frontend_script` draws them on a canvas laid over the
video. The video itself goes back unmodified, so the overlay stays sharp and
costs no re-encoding.
"""

import json
from typing import Optional

import av
import cv2
import numpy as np
import streamlit as st
from streamlit_webrtc import WebRtcMode, WebRtcStreamerContext, webrtc_streamer

st.title("Client-side detection overlay")

min_area = st.slider("Minimum box area (% of the frame)", 0.1, 10.0, 0.5, 0.1)

FRONTEND_SCRIPT = """
export default function ({ channels, root }) {
  root.style.cssText = "position: absolute; inset: 0; pointer-events: none";
  const canvas = document.createElement("canvas");
  canvas.style.cssText = "width: 100%; height: 100%";
  root.appendChild(canvas);
  const ctx = canvas.getContext("2d");

  const resizeObserver = new ResizeObserver(() => {
    canvas.width = root.clientWidth * devicePixelRatio;
    canvas.height = root.clientHeight * devicePixelRatio;
  });
  resizeObserver.observe(root);

  channels.detections.addEventListener("message", (event) => {
    const { boxes } = JSON.parse(event.data);
    const { width, height } = canvas;
    ctx.clearRect(0, 0, width, height);
    ctx.lineWidth = 2 * devicePixelRatio;
    ctx.strokeStyle = "#ff4081";
    ctx.fillStyle = "#ff4081";
    ctx.font = `${12 * devicePixelRatio}px sans-serif`;
    for (const { x, y, w, h, label } of boxes) {
      ctx.strokeRect(x * width, y * height, w * width, h * height);
      ctx.fillText(label, x * width, y * height - 4 * devicePixelRatio);
    }
  });

  return () => resizeObserver.disconnect();
}
"""

background_subtractor = cv2.createBackgroundSubtractorMOG2(detectShadows=False)

# Frames can reach the callback before this script run gets to assign the
# context returned by `webrtc_streamer()` at the bottom.
ctx: Optional[WebRtcStreamerContext] = None


def video_frame_callback(frame: av.VideoFrame) -> av.VideoFrame:
    image = frame.to_ndarray(format="bgr24")
    height, width = image.shape[:2]

    mask = background_subtractor.apply(image)
    mask = cv2.dilate(mask, np.ones((5, 5), np.uint8), iterations=2)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    boxes = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        area_percent = 100 * w * h / (width * height)
        if area_percent < min_area:
            continue
        boxes.append(
            {
                "x": x / width,
                "y": y / height,
                "w": w / width,
                "h": h / height,
                "label": f"motion {area_percent:.1f}%",
            }
        )

    channels = ctx.data_channels if ctx else None
    if channels and "detections" in channels:
        channels["detections"].send(json.dumps({"boxes": boxes}))

    return frame


ctx = webrtc_streamer(
    key="data-channel-overlay",
    mode=WebRtcMode.SENDRECV,
    media_stream_constraints={"video": True, "audio": False},
    video_frame_callback=video_frame_callback,
    # Only the latest boxes matter, so a lost or late message is better
    # skipped than retransmitted.
    data_channels={"detections": {"ordered": False, "maxRetransmits": 0}},
    frontend_script=FRONTEND_SCRIPT,
)
