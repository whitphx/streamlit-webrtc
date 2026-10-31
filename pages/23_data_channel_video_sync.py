"""Detection boxes drawn over the very video frame they were found in.

The server renders bouncing balls, finds them again with an OpenCV colour
detector, and sends each frame's boxes stamped with the RTP timestamp the
frame is sent under. The browser draws the boxes when the frame with that
timestamp is presented, using `createPlayoutClock("video")` in a
`requestVideoFrameCallback()` loop. Switch to drawing on arrival to see the
boxes lead the balls, or add a simulated delay to the data to see them trail.
"""

import fractions
import json
import math
from typing import Optional

import av
import cv2
import numpy as np
import streamlit as st
from streamlit_webrtc import (
    WebRtcMode,
    WebRtcStreamerContext,
    create_video_source_track,
    webrtc_streamer,
)

st.title("Data synced to video frames")

draw_on = st.radio(
    "Draw the boxes",
    ["In sync with the video", "On arrival"],
    horizontal=True,
)
extra_delay_ms = st.number_input(
    "Simulated extra delay of the data channel (ms)",
    min_value=0,
    max_value=1000,
    value=0,
    step=50,
)
hold_for_data = st.checkbox(
    "Delay the video when the boxes arrive too late for it (holdForData)",
)

WIDTH, HEIGHT = 640, 360
FPS = 30
# Hue (OpenCV's 0-179 scale), radius and speed in pixels per second.
BALLS = [(0, 28, (420, 260)), (60, 22, (-380, 300)), (120, 34, (300, -220))]

FRONTEND_SCRIPT = """
export default function ({ channels, root, media, createPlayoutClock, data }) {
  root.style.cssText = "position: absolute; inset: 0; pointer-events: none";
  const canvas = document.createElement("canvas");
  canvas.style.cssText = "width: 100%; height: 100%";
  root.appendChild(canvas);
  const ctx = canvas.getContext("2d");
  const status = document.createElement("div");
  status.style.cssText =
    "position: absolute; left: 8px; bottom: 8px; padding: 2px 6px;" +
    "font: 12px monospace; color: #fff; background: rgba(0, 0, 0, 0.6)";
  root.appendChild(status);

  const resizeObserver = new ResizeObserver(() => {
    canvas.width = root.clientWidth * devicePixelRatio;
    canvas.height = root.clientHeight * devicePixelRatio;
  });
  resizeObserver.observe(root);

  let options = data;
  let clock = createPlayoutClock("video", {
    holdForData: options.holdForData ? {} : undefined,
  });
  const queue = [];

  const draw = (detection) => {
    const { width, height } = canvas;
    ctx.clearRect(0, 0, width, height);
    ctx.lineWidth = 3 * devicePixelRatio;
    ctx.strokeStyle = "#fff";
    for (const [x, y, w, h] of detection.boxes) {
      ctx.strokeRect(x * width, y * height, w * width, h * height);
    }
    // Which frame's boxes are on screen, for scripts/measure_av_sync.py.
    canvas.dataset.rtpTimestamp = String(detection.rtpTimestamp);
  };

  channels.boxes.addEventListener("message", ({ data }) => {
    const detection = JSON.parse(data);
    // Stands in for a slower network path for the data than for the video.
    setTimeout(() => {
      clock.noteDataArrival(detection.rtpTimestamp);
      if (options.sync) queue.push(detection);
      else draw(detection);
    }, options.extraDelayMs);
  });

  // The boxes are drawn in the same rendering step that presents the frame,
  // and `expectedDisplayTime` is when both become visible.
  let frameCallback;
  const onFrame = (now, metadata) => {
    frameCallback = media.video.requestVideoFrameCallback(onFrame);
    let due;
    while (queue.length > 0) {
      const dueAt = clock.playoutTime(queue[0].rtpTimestamp);
      if (dueAt === null || dueAt > metadata.expectedDisplayTime) break;
      due = queue.shift();
    }
    if (due) draw(due);
    const { supported, targetMs } = clock.hold();
    status.textContent =
      (options.sync ? "drawn with its frame" : "drawn on arrival") +
      (supported ? `, video held ${(targetMs ?? 0).toFixed(0)} ms` : "");
  };
  frameCallback = media.video.requestVideoFrameCallback(onFrame);

  return {
    update(newData) {
      if (newData.holdForData !== options.holdForData) {
        clock.close();
        clock = createPlayoutClock("video", {
          holdForData: newData.holdForData ? {} : undefined,
        });
      }
      if (!newData.sync) queue.length = 0;
      options = newData;
    },
    cleanup() {
      media.video.cancelVideoFrameCallback(frameCallback);
      resizeObserver.disconnect();
      clock.close();
    },
  };
}
"""

# Frames can reach the callback before this script run gets to assign the
# context returned by `webrtc_streamer()` at the bottom.
ctx: Optional[WebRtcStreamerContext] = None


def bounce(position: float, limit: float) -> float:
    period = position % (2 * limit)
    return period if period < limit else 2 * limit - period


def hue_to_bgr(hue: int) -> list:
    hsv = np.array([[[hue, 220, 230]]], dtype=np.uint8)
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)[0, 0].tolist()


BALL_COLORS = [hue_to_bgr(hue) for hue, _, _ in BALLS]


def detect_balls(image: np.ndarray) -> list:
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array([0, 120, 120]), np.array([179, 255, 255]))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        boxes.append([x / WIDTH, y / HEIGHT, w / WIDTH, h / HEIGHT])
    return boxes


def video_source_callback(pts: int, time_base: fractions.Fraction) -> av.VideoFrame:
    t = float(pts * time_base)
    image = np.full((HEIGHT, WIDTH, 3), 40, dtype=np.uint8)
    for (hue, radius, (vx, vy)), color in zip(BALLS, BALL_COLORS):
        x = radius + bounce(vx * t + 100 * hue, WIDTH - 2 * radius)
        y = radius + bounce(vy * t + 50 * hue, HEIGHT - 2 * radius)
        cv2.circle(image, (math.floor(x), math.floor(y)), radius, color, cv2.FILLED)

    channels = ctx.data_channels if ctx else None
    # None until the sender has encoded its first frame.
    rtp_timestamp = ctx.rtp_timestamp("video", pts, time_base) if ctx else None
    if channels and "boxes" in channels and rtp_timestamp is not None:
        channels["boxes"].send(
            json.dumps({"rtpTimestamp": rtp_timestamp, "boxes": detect_balls(image)})
        )

    return av.VideoFrame.from_ndarray(image, format="bgr24")


video_source_track = create_video_source_track(
    video_source_callback, key="video-sync-demo-video", fps=FPS
)

ctx = webrtc_streamer(
    key="data-channel-video-sync",
    mode=WebRtcMode.RECVONLY,
    source_video_track=video_source_track,
    media_stream_constraints={"video": True, "audio": False},
    data_channels={"boxes": {}},
    frontend_script=FRONTEND_SCRIPT,
    frontend_data={
        "sync": draw_on == "In sync with the video",
        "extraDelayMs": extra_delay_ms,
        "holdForData": hold_for_data,
    },
)
