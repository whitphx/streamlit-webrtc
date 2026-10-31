"""Measure how far the A/V sync samples draw their data from the media.

Runs `pages/22_data_channel_audio_sync.py` and
`pages/23_data_channel_video_sync.py` in headless Chromium against a local
Streamlit server, under each drawing mode and simulated data channel delay,
and prints the error of what is drawn against the media it belongs to.
A positive error means the data is shown before its media.

Audio: each beat count shown, against the click's onset as heard on the
received track by a Web Audio worklet, plus the output delay the browser
reports for the audio element. Video: the boxes on screen at each presented
frame, against the frame's own RTP timestamp.

Build the frontend first (`cd streamlit_webrtc/frontend && pnpm run build`),
then run

    uv run --with playwright playwright install chromium
    uv run --with playwright python scripts/measure_av_sync.py

or pass `--executable-path` to use a Chromium that is already installed.
"""

import argparse
import contextlib
import re
import socket
import statistics
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Iterator, List, NamedTuple, Optional

from playwright.sync_api import Frame, Page, sync_playwright

ROOT = Path(__file__).resolve().parent.parent

# Keeps every peer connection the page makes, so the probes can read stats.
INIT_SCRIPT = """
window.__pcs = [];
const NativePeerConnection = window.RTCPeerConnection;
window.RTCPeerConnection = function (...args) {
  const pc = new NativePeerConnection(...args);
  window.__pcs.push(pc);
  return pc;
};
window.RTCPeerConnection.prototype = NativePeerConnection.prototype;
"""

AUDIO_PROBE = """
async () => {
  const probe = (window.__avsync = { onsets: [], shown: [] });
  const audio = document.querySelector("audio");
  const context = new AudioContext();
  const worklet = `registerProcessor("onset", class extends AudioWorkletProcessor {
    quiet = 0;
    process([input]) {
      for (const sample of input[0] ?? []) {
        if (Math.abs(sample) > 0.05) {
          if (this.quiet > sampleRate * 0.3) this.port.postMessage(null);
          this.quiet = 0;
        } else {
          this.quiet++;
        }
      }
      return true;
    }
  });`;
  await context.audioWorklet.addModule(
    "data:text/javascript," + encodeURIComponent(worklet),
  );
  const node = new AudioWorkletNode(context, "onset");
  node.port.onmessage = () => probe.onsets.push(performance.now());
  context.createMediaStreamSource(audio.srcObject).connect(node);
  node.connect(context.destination);
  new MutationObserver(() => probe.shown.push(performance.now())).observe(
    document.querySelector(".beat"),
    { childList: true, characterData: true, subtree: true },
  );
}
"""

PLAYOUT_STATS = """
async () => {
  for (const pc of window.__pcs) {
    if (pc.signalingState === "closed") continue;
    for (const report of (await pc.getStats()).values()) {
      if (report.type === "media-playout") {
        return [report.totalPlayoutDelay, report.totalSamplesCount];
      }
    }
  }
  return null;
}
"""

VIDEO_PROBE = """
() => {
  const probe = (window.__avsync = { errors: [] });
  const video = document.querySelector("video");
  const canvas = document.querySelector("canvas");
  // Registered after the sample's own callback, so it runs after the sample
  // has drawn for the same frame.
  const onFrame = (now, metadata) => {
    video.requestVideoFrameCallback(onFrame);
    const drawn = canvas.dataset.rtpTimestamp;
    if (drawn === undefined || metadata.rtpTimestamp === undefined) return;
    const delta =
      ((((Number(drawn) - metadata.rtpTimestamp) % 2 ** 32) + 2 ** 32 + 2 ** 31) %
        2 ** 32) -
      2 ** 31;
    probe.errors.push(delta / 90);
  };
  video.requestVideoFrameCallback(onFrame);
}
"""


class Condition(NamedTuple):
    sync: bool
    delay_ms: int
    hold: bool

    def __str__(self) -> str:
        mode = "synced" if self.sync else "arrival"
        hold = " + holdForData" if self.hold else ""
        return f"{mode}{hold}, data delayed {self.delay_ms} ms"


CONDITIONS = [
    Condition(sync=True, delay_ms=0, hold=False),
    Condition(sync=False, delay_ms=0, hold=False),
    Condition(sync=True, delay_ms=150, hold=False),
    Condition(sync=False, delay_ms=150, hold=False),
    Condition(sync=True, delay_ms=150, hold=True),
]


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@contextlib.contextmanager
def streamlit_server() -> Iterator[str]:
    port = free_port()
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "home.py",
            "--server.address=127.0.0.1",
            f"--server.port={port}",
            "--server.headless=true",
            "--browser.gatherUsageStats=false",
        ],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + 60
        while True:
            try:
                urllib.request.urlopen(f"{url}/_stcore/health", timeout=1)
                break
            except OSError:
                if time.monotonic() > deadline or process.poll() is not None:
                    raise RuntimeError("Streamlit did not start")
                time.sleep(0.5)
        yield url
    finally:
        process.terminate()
        try:
            process.wait(10)
        except subprocess.TimeoutExpired:
            process.kill()


def start_sample(page: Page, url: str) -> Frame:
    page.goto(url)
    iframe = page.locator('iframe[title*="streamlit_webrtc"]').first
    iframe.wait_for(timeout=60000)
    frame = iframe.element_handle().content_frame()
    assert frame is not None
    frame.get_by_role("button", name=re.compile("start", re.I)).click(timeout=60000)
    frame.wait_for_function(
        "() => [...document.querySelectorAll('audio, video')]"
        ".some((m) => m.srcObject && !m.paused && m.currentTime > 1)",
        timeout=60000,
    )
    return frame


def apply(page: Page, condition: Condition, sync_label: str) -> None:
    page.get_by_text(sync_label if condition.sync else "On arrival").click()
    delay = page.get_by_label("Simulated extra delay of the data channel (ms)")
    delay.fill(str(condition.delay_ms))
    delay.press("Enter")
    checkbox = page.get_by_role("checkbox")
    if checkbox.is_checked() != condition.hold:
        page.get_by_text("holdForData").click()
    page.wait_for_timeout(1000)


def summarize(errors: List[float]) -> str:
    if not errors:
        return "no samples"
    errors = sorted(errors)
    p5 = errors[int(0.05 * (len(errors) - 1))]
    p95 = errors[int(0.95 * (len(errors) - 1))]
    return (
        f"n={len(errors):5d}  median {statistics.median(errors):+7.1f} ms  "
        f"p5 {p5:+7.1f}  p95 {p95:+7.1f}"
    )


def measure_audio(page: Page, frame: Frame, seconds: float) -> List[float]:
    frame.evaluate("() => { window.__avsync.onsets = []; window.__avsync.shown = []; }")
    before = frame.evaluate(PLAYOUT_STATS)
    page.wait_for_timeout(seconds * 1000)
    after = frame.evaluate(PLAYOUT_STATS)
    probe = frame.evaluate("() => window.__avsync")
    # Web Audio hears the track before the output device plays it.
    output_delay_ms = 0.0
    if before and after and after[1] > before[1]:
        output_delay_ms = 1000 * (after[0] - before[0]) / (after[1] - before[1])
    errors = []
    for shown in probe["shown"]:
        nearest: Optional[float] = min(
            probe["onsets"], key=lambda onset: abs(onset - shown), default=None
        )
        # Beats are a second apart, so anything nearer than half of that is
        # the same beat.
        if nearest is not None and abs(nearest - shown) < 500:
            errors.append(nearest + output_delay_ms - shown)
    return errors


def measure_video(page: Page, frame: Frame, seconds: float) -> List[float]:
    frame.evaluate("() => { window.__avsync.errors = []; }")
    page.wait_for_timeout(seconds * 1000)
    return frame.evaluate("() => window.__avsync.errors")


def report(frame: Frame, kind: str, condition: Condition, errors: List[float]) -> None:
    target = frame.evaluate(
        """(kind) => window.__pcs
          .filter((pc) => pc.signalingState !== "closed")
          .flatMap((pc) => pc.getReceivers())
          .find((r) => r.track.kind === kind)?.jitterBufferTarget ?? null""",
        kind,
    )
    hold = f"  (held {target:.0f} ms)" if target is not None else ""
    print(f"  {condition!s:42}  {summarize(errors)}{hold}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--executable-path", help="the Chromium to run")
    parser.add_argument(
        "--seconds", type=float, default=20, help="measuring time per condition"
    )
    parser.add_argument(
        "--warmup", type=float, default=15, help="settling time per condition"
    )
    args = parser.parse_args()

    with streamlit_server() as url, sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=args.executable_path,
            args=["--autoplay-policy=no-user-gesture-required"],
        )
        try:
            page = browser.new_page()
            page.add_init_script(INIT_SCRIPT)

            print("Audio: click heard minus beat shown")
            frame = start_sample(page, f"{url}/data_channel_audio_sync")
            frame.evaluate(AUDIO_PROBE)
            for condition in CONDITIONS:
                apply(page, condition, "In sync with the audio")
                page.wait_for_timeout(args.warmup * 1000)
                errors = measure_audio(page, frame, args.seconds)
                report(frame, "audio", condition, errors)

            print("Video: frame of the boxes on screen minus frame on screen")
            frame = start_sample(page, f"{url}/data_channel_video_sync")
            frame.evaluate(VIDEO_PROBE)
            for condition in CONDITIONS:
                apply(page, condition, "In sync with the video")
                page.wait_for_timeout(args.warmup * 1000)
                errors = measure_video(page, frame, args.seconds)
                report(frame, "video", condition, errors)
        finally:
            browser.close()


if __name__ == "__main__":
    main()
