"""Binary data channel messages decoded and drawn in the browser, in sync
with the audio the same connection carries.

The server generates a tone sweep and, for every other 20 ms audio frame,
sends the frame's spectrum as a small binary struct. The browser decodes it
with a `DataView` and draws it on a canvas when the audio it describes plays.
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

st.title("Binary data channel messages synced to audio")
st.warning("This demo plays a tone. Check your volume before starting.")

SAMPLE_RATE = 48000
PTIME = 0.020
SAMPLES_PER_FRAME = int(SAMPLE_RATE * PTIME)
NUM_BANDS = 32
# A sequence number, the RTP timestamp the frame's audio plays under, then the
# band magnitudes.
SPECTRUM_STRUCT = struct.Struct(f"<II{NUM_BANDS}f")

FRONTEND_SCRIPT = """
const NUM_BANDS = __NUM_BANDS__;

export default function ({ channels, root, media, createPlayoutClock }) {
  const canvas = document.createElement("canvas");
  canvas.width = 640;
  canvas.height = 200;
  canvas.style.cssText = "width: 100%; background: #111";
  const status = document.createElement("div");
  status.style.cssText = "font: 12px monospace; padding: 4px 0";
  root.append(canvas, status);
  const ctx = canvas.getContext("2d");

  // Each message carries the RTP timestamp of its audio, and the clock
  // tells when the audio with that timestamp is heard.
  const clock = createPlayoutClock("audio");
  const queue = [];
  let received = 0;
  channels.spectrum.addEventListener("message", ({ data }) => {
    const view = new DataView(data);
    queue.push({
      arrival: performance.now(),
      rtpTimestamp: view.getUint32(4, true),
      seq: view.getUint32(0, true),
      bands: new Float32Array(data, 8, NUM_BANDS),
    });
    received++;
  });

  let animationFrame;
  const draw = () => {
    animationFrame = requestAnimationFrame(draw);
    // A paused live stream resumes at the live edge, so the spectra of the
    // audio missed meanwhile are never due.
    if (media.audio.srcObject && media.audio.paused) {
      queue.length = 0;
      status.textContent = "paused";
      return;
    }
    let frame;
    while (queue.length > 0) {
      const dueAt = clock.playoutTime(queue[0].rtpTimestamp);
      if (dueAt === null || dueAt > performance.now()) break;
      frame = { ...queue.shift(), dueAt };
    }
    if (!frame) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const barWidth = canvas.width / NUM_BANDS;
    frame.bands.forEach((magnitude, i) => {
      const barHeight = Math.min(1, magnitude) * canvas.height;
      ctx.fillStyle = `hsl(${(i / NUM_BANDS) * 280}, 80%, 55%)`;
      ctx.fillRect(i * barWidth + 1, canvas.height - barHeight, barWidth - 2, barHeight);
    });
    status.textContent =
      `frame #${frame.seq}, ${received} received, ` +
      `drawn ${(frame.dueAt - frame.arrival).toFixed(0)} ms after arrival to match the audio`;
  };
  draw();

  return () => {
    cancelAnimationFrame(animationFrame);
    clock.close();
  };
}
""".replace("__NUM_BANDS__", str(NUM_BANDS))

# Frames can reach the callback before this script run gets to assign the
# context returned by `webrtc_streamer()` at the bottom.
ctx: Optional[WebRtcStreamerContext] = None

band_edges = np.geomspace(2, SAMPLES_PER_FRAME // 2, NUM_BANDS + 1).astype(int)


def audio_source_callback(pts: int, time_base: fractions.Fraction) -> av.AudioFrame:
    t = float(pts * time_base) + np.arange(SAMPLES_PER_FRAME) / SAMPLE_RATE
    # A tone sweeping 200 Hz -> 3.2 kHz every 4 seconds, plus its octave.
    # The phase is the integral of the frequency 200 * 2 ** (t % 4).
    phase = 2 * np.pi * 200 * (2 ** (t % 4) - 1) / np.log(2)
    samples = 0.3 * np.sin(phase) + 0.15 * np.sin(2 * phase)

    seq = pts // SAMPLES_PER_FRAME
    channels = ctx.data_channels if ctx else None
    # None until the sender has encoded its first frame.
    rtp_timestamp = ctx.rtp_timestamp("audio", pts, time_base) if ctx else None
    if (
        channels
        and "spectrum" in channels
        and seq % 2 == 0
        and rtp_timestamp is not None
    ):
        spectrum = np.abs(np.fft.rfft(samples)) / (SAMPLES_PER_FRAME / 4)
        bands = [
            spectrum[lo : max(hi, lo + 1)].max()
            for lo, hi in zip(band_edges, band_edges[1:])
        ]
        channels["spectrum"].send(SPECTRUM_STRUCT.pack(seq, rtp_timestamp, *bands))

    frame = av.AudioFrame.from_ndarray(
        (samples * 32767).astype(np.int16).reshape(1, -1), format="s16", layout="mono"
    )
    frame.sample_rate = SAMPLE_RATE
    return frame


audio_source_track = create_audio_source_track(
    audio_source_callback, key="binary-demo-audio", sample_rate=SAMPLE_RATE, ptime=PTIME
)

ctx = webrtc_streamer(
    key="data-channel-binary",
    mode=WebRtcMode.RECVONLY,
    source_audio_track=audio_source_track,
    media_stream_constraints={"video": False, "audio": True},
    data_channels={"spectrum": {"ordered": False, "maxRetransmits": 0}},
    frontend_script=FRONTEND_SCRIPT,
)
