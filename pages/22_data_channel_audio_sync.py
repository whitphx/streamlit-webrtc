"""Data channel messages shown when the audio they describe is heard.

The server plays a click track and sends, for every 20 ms audio frame, the
frame's level and beat number stamped with the RTP timestamp the frame's
audio plays under. The browser holds each message until
`createPlayoutClock("audio")` says its audio is heard, so the beat count
flashes with the click. Switch to drawing on arrival to see the count run
ahead of the click, and add a simulated delay to the data to see it fall
behind.
"""

import fractions
import struct
from typing import Optional

import av
import numpy as np
import streamlit as st
from streamlit_webrtc import (
    WebRtcMode,
    WebRtcStreamerContext,
    create_audio_source_track,
    webrtc_streamer,
)

st.title("Data synced to audio playout")
st.warning("This demo plays clicks. Check your volume before starting.")

draw_on = st.radio(
    "Draw the data",
    ["In sync with the audio", "On arrival"],
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
    "Delay the audio when the data arrives too late for it (holdForData)",
)

SAMPLE_RATE = 48000
PTIME = 0.020
SAMPLES_PER_FRAME = int(SAMPLE_RATE * PTIME)
FRAMES_PER_BEAT = 50
BEATS_PER_BAR = 4
CLICK_SAMPLES = SAMPLE_RATE * 60 // 1000
# The RTP timestamp the frame's audio plays under, its level, and its beat
# number from 1, or 0 for a frame that starts no beat.
FRAME_STRUCT = struct.Struct("<IfB")

FRONTEND_SCRIPT = """
const HISTORY = 150;

export default function ({ channels, root, media, createPlayoutClock, data }) {
  root.style.cssText = "font: 14px sans-serif";
  const beat = document.createElement("div");
  beat.className = "beat";
  beat.style.cssText =
    "font: bold 96px sans-serif; text-align: center; line-height: 1.4;" +
    "color: #fff; background: #222; transition: background 0.15s";
  const canvas = document.createElement("canvas");
  canvas.width = 600;
  canvas.height = 80;
  canvas.style.cssText = "width: 100%; height: 80px; background: #111";
  const status = document.createElement("div");
  status.style.cssText = "font: 12px monospace; padding: 4px 0";
  root.append(beat, canvas, status);
  const ctx = canvas.getContext("2d");

  let options = data;
  let clock = createPlayoutClock("audio", {
    holdForData: options.holdForData ? {} : undefined,
  });
  const queue = [];
  const levels = [];
  let lead = null;

  channels.frames.addEventListener("message", ({ data }) => {
    const view = new DataView(data);
    const frame = {
      rtpTimestamp: view.getUint32(0, true),
      level: view.getFloat32(4, true),
      beat: view.getUint8(8),
    };
    // Stands in for a slower network path for the data than for the audio.
    setTimeout(() => {
      frame.arrival = performance.now();
      clock.noteDataArrival(frame.rtpTimestamp, frame.arrival);
      queue.push(frame);
    }, options.extraDelayMs);
  });

  const show = (frame) => {
    levels.push(frame.level);
    if (levels.length > HISTORY) levels.shift();
    if (frame.beat) {
      beat.textContent = String(frame.beat);
      beat.style.background = frame.beat === 1 ? "#d81b60" : "#1e88e5";
      setTimeout(() => (beat.style.background = "#222"), 100);
    }
  };

  let animationFrame;
  const draw = () => {
    animationFrame = requestAnimationFrame(draw);
    // A paused live stream resumes at the live edge, so the data of the
    // audio missed meanwhile is never due.
    if (media.audio.srcObject && media.audio.paused) {
      queue.length = 0;
      return;
    }
    const now = performance.now();
    while (queue.length > 0) {
      if (options.sync) {
        const dueAt = clock.playoutTime(queue[0].rtpTimestamp);
        if (dueAt === null || dueAt > now) break;
        lead = dueAt - queue[0].arrival;
      }
      show(queue.shift());
    }
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#43a047";
    const barWidth = canvas.width / HISTORY;
    levels.forEach((level, i) => {
      const height = Math.min(1, level * 3) * canvas.height;
      ctx.fillRect(i * barWidth, canvas.height - height, barWidth, height);
    });
    const { supported, targetMs } = clock.hold();
    status.textContent =
      (options.sync && lead !== null
        ? `drawn ${lead.toFixed(0)} ms after arrival`
        : "drawn on arrival") +
      (supported ? `, audio held ${(targetMs ?? 0).toFixed(0)} ms` : "");
  };
  draw();

  return {
    update(newData) {
      if (newData.holdForData !== options.holdForData) {
        clock.close();
        clock = createPlayoutClock("audio", {
          holdForData: newData.holdForData ? {} : undefined,
        });
      }
      options = newData;
      lead = null;
    },
    cleanup() {
      cancelAnimationFrame(animationFrame);
      clock.close();
    },
  };
}
"""

# Frames can reach the callback before this script run gets to assign the
# context returned by `webrtc_streamer()` at the bottom.
ctx: Optional[WebRtcStreamerContext] = None

click_envelope = np.exp(-np.arange(CLICK_SAMPLES) / (CLICK_SAMPLES / 6))


def audio_source_callback(pts: int, time_base: fractions.Fraction) -> av.AudioFrame:
    frame_index = pts // SAMPLES_PER_FRAME
    beat_frame = frame_index % FRAMES_PER_BEAT
    beat = (frame_index // FRAMES_PER_BEAT) % BEATS_PER_BAR + 1

    samples = np.zeros(SAMPLES_PER_FRAME)
    # Each click starts on the first sample of its frame, so the beat's
    # message carries the RTP timestamp of the click's onset.
    start = beat_frame * SAMPLES_PER_FRAME
    if start < CLICK_SAMPLES:
        t = np.arange(start, min(start + SAMPLES_PER_FRAME, CLICK_SAMPLES))
        pitch = 1760 if beat == 1 else 880
        samples[: len(t)] = (
            0.5 * click_envelope[t] * np.sin(2 * np.pi * pitch * t / SAMPLE_RATE)
        )

    channels = ctx.data_channels if ctx else None
    # None until the sender has encoded its first frame.
    rtp_timestamp = ctx.rtp_timestamp("audio", pts, time_base) if ctx else None
    if channels and "frames" in channels and rtp_timestamp is not None:
        level = float(np.sqrt(np.mean(samples**2)))
        channels["frames"].send(
            FRAME_STRUCT.pack(rtp_timestamp, level, beat if beat_frame == 0 else 0)
        )

    frame = av.AudioFrame.from_ndarray(
        (samples * 32767).astype(np.int16).reshape(1, -1), format="s16", layout="mono"
    )
    frame.sample_rate = SAMPLE_RATE
    return frame


audio_source_track = create_audio_source_track(
    audio_source_callback,
    key="audio-sync-demo-audio",
    sample_rate=SAMPLE_RATE,
    ptime=PTIME,
)

ctx = webrtc_streamer(
    key="data-channel-audio-sync",
    mode=WebRtcMode.RECVONLY,
    source_audio_track=audio_source_track,
    media_stream_constraints={"video": False, "audio": True},
    # Ordered and reliable, because a lost beat would leave a gap in the count
    # and the messages are small enough to retransmit in time.
    data_channels={"frames": {}},
    frontend_script=FRONTEND_SCRIPT,
    frontend_data={
        "sync": draw_on == "In sync with the audio",
        "extraDelayMs": extra_delay_ms,
        "holdForData": hold_for_data,
    },
)
