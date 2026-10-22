"""Browser pointer and key events sent to the server over data channels.

The events reach the server without a script rerun, so they can steer a
server-generated video stream at the browser's event rate. Click the video
to focus it before typing.
"""

import fractions
import json
import threading

import av
import cv2
import numpy as np
import streamlit as st
from streamlit_webrtc import (
    DataChannel,
    DataChannelMessage,
    WebRtcMode,
    create_video_source_track,
    webrtc_streamer,
)

st.title("Browser input events over data channels")

FRONTEND_SCRIPT = """
export default function ({ channels, root }) {
  root.style.cssText = "position: absolute; inset: 0; cursor: crosshair; outline: none";
  root.tabIndex = 0;
  const status = document.createElement("div");
  status.style.cssText =
    "position: absolute; left: 8px; bottom: 8px; padding: 2px 6px;" +
    "font: 12px monospace; color: #fff; background: rgba(0, 0, 0, 0.6)";
  status.textContent = "Click to focus, then type";
  root.appendChild(status);

  const sendPointer = (event, type) => {
    if (channels.pointer.readyState !== "open") return;
    const rect = root.getBoundingClientRect();
    channels.pointer.send(JSON.stringify({
      type,
      x: (event.clientX - rect.left) / rect.width,
      y: (event.clientY - rect.top) / rect.height,
    }));
  };
  // The same root serves every session, so the cleanup removes these.
  const listeners = new AbortController();
  const { signal } = listeners;
  root.addEventListener("pointermove", (event) => sendPointer(event, "move"), { signal });
  root.addEventListener("pointerdown", (event) => {
    root.focus();
    sendPointer(event, "down");
  }, { signal });
  root.addEventListener("keydown", (event) => {
    // Only the keys the server types are taken from the browser, so that
    // Tab still moves focus out of the overlay and shortcuts keep working.
    if (channels.keys.readyState !== "open" || event.ctrlKey || event.metaKey) return;
    channels.keys.send(event.key);
    if (event.key === "Backspace" || event.key.length === 1) event.preventDefault();
  }, { signal });
  channels.keys.addEventListener("message", (event) => {
    const { typed, events } = JSON.parse(event.data);
    status.textContent = `server got ${events} events, typed: ${typed}`;
  });
  return () => listeners.abort();
}
"""


class ControlState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.pointer = (0.5, 0.5)
        self.clicks: list[tuple[float, float]] = []
        self.typed = ""
        self.events = 0


# Both callbacks below run outside the script thread, so they share this
# object instead of `st.session_state`.
if "control_state" not in st.session_state:
    st.session_state["control_state"] = ControlState()
state: ControlState = st.session_state["control_state"]


def on_data_channel_message(channel: DataChannel, message: DataChannelMessage) -> None:
    with state.lock:
        state.events += 1
        if channel.label == "pointer":
            event = json.loads(message)
            state.pointer = (event["x"], event["y"])
            if event["type"] == "down":
                state.clicks = [*state.clicks[-9:], state.pointer]
        elif channel.label == "keys":
            key = message if isinstance(message, str) else message.decode()
            if key == "Backspace":
                state.typed = state.typed[:-1]
            elif len(key) == 1:
                state.typed = (state.typed + key)[-30:]
            channel.send(json.dumps({"typed": state.typed, "events": state.events}))


def video_source_callback(pts: int, time_base: fractions.Fraction) -> av.VideoFrame:
    height, width = 360, 640
    image = np.full((height, width, 3), 32, dtype=np.uint8)
    with state.lock:
        pointer, clicks, typed = state.pointer, list(state.clicks), state.typed
    for x, y in clicks:
        cv2.circle(image, (int(x * width), int(y * height)), 6, (0, 160, 255), -1)
    cv2.circle(
        image, (int(pointer[0] * width), int(pointer[1] * height)), 12, (0, 255, 0), 2
    )
    cv2.putText(
        image, typed, (16, 48), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 2
    )
    return av.VideoFrame.from_ndarray(image, format="bgr24")


video_source_track = create_video_source_track(
    video_source_callback, key="controls-demo-video", fps=30
)

webrtc_streamer(
    key="data-channel-controls",
    mode=WebRtcMode.RECVONLY,
    source_video_track=video_source_track,
    media_stream_constraints={"video": True, "audio": False},
    video_html_attrs={"autoPlay": True, "muted": True, "style": {"width": "100%"}},
    on_data_channel_message=on_data_channel_message,
    data_channels={
        # A pointer position is superseded by the next one, so it is not
        # worth retransmitting; keystrokes must all arrive, in order.
        "pointer": {"ordered": False, "maxRetransmits": 0},
        "keys": {},
    },
    frontend_script=FRONTEND_SCRIPT,
)
