// A receiver reports one RTP timestamp per packet, while it hands media to
// playout in smaller pieces: a 20 ms Opus packet goes out as two 10 ms frames
// with the same timestamp. Only the earliest delivery seen for a packet
// marks when its first sample played, so the clock keeps the earliest
// estimate over a window several packets long.
const WINDOW_MS = 300;
// Presented video frames are kept longer, so that data arriving after its
// frame still finds the exact time the frame was shown.
const FRAME_WINDOW_MS = 2000;
// A slow stream presents only a few frames per second, so a window as short
// as the audio's would often hold none.
const RECENT_FRAMES_MS = 1000;
const SAMPLE_INTERVAL_MS = 10;
const STATS_INTERVAL_MS = 1000;
const DEFAULT_CLOCK_RATES = { audio: 48000, video: 90000 } as const;

export interface PlayoutClock {
  /** The `performance.now()` time at which the received media with this RTP
   * timestamp is heard or shown, or `null` until the media plays. */
  playoutTime(rtpTimestamp: number): number | null;
  close(): void;
}

interface Estimate {
  at: number;
  rtp: number;
  time: number;
}

function wrapDelta(a: number, b: number): number {
  return ((((a - b) % 2 ** 32) + 2 ** 32 + 2 ** 31) % 2 ** 32) - 2 ** 31;
}

// Where `rtp` falls on the earliest timeline that the estimates allow.
function extrapolate(
  estimates: Estimate[],
  rtp: number,
  msPerTick: number,
): number {
  const latest = estimates[estimates.length - 1];
  let earliest = Infinity;
  for (const e of estimates) {
    earliest = Math.min(
      earliest,
      e.time - wrapDelta(e.rtp, latest.rtp) * msPerTick,
    );
  }
  return earliest + wrapDelta(rtp, latest.rtp) * msPerTick;
}

export function createPlayoutClock(
  pc: RTCPeerConnection,
  kind: "audio" | "video",
  video?: HTMLVideoElement,
): PlayoutClock {
  // Each estimate is the time the receiver handed RTP timestamp `rtp` to its track.
  let estimates: Estimate[] = [];
  // Each frame is the time the video element showed RTP timestamp `rtp`.
  let frames: Estimate[] = [];
  let clockRate: number | null = null;
  let outputDelayMs: number | null = null;
  let previousPlayout: { delay: number; samples: number } | null = null;
  let closed = false;

  function stop() {
    closed = true;
    clearInterval(timer);
    clearInterval(statsTimer);
    if (frameCallback !== null) video?.cancelVideoFrameCallback(frameCallback);
    frameCallback = null;
    estimates = [];
    frames = [];
  }

  // The element reports the RTP timestamp of each frame it presents and when
  // the frame becomes visible, after decoding and rendering, which the
  // receiver's own estimates cannot see.
  // https://wicg.github.io/video-rvfc/#dom-videoframecallbackmetadata-rtptimestamp
  let frameCallback: number | null = null;
  function onVideoFrame(now: number, metadata: VideoFrameCallbackMetadata) {
    if (pc.signalingState === "closed") {
      stop();
      return;
    }
    // A browser that leaves the field out does so for every frame, and the
    // clock then runs on the receiver's estimates alone.
    if (metadata.rtpTimestamp === undefined || !video) {
      frameCallback = null;
      return;
    }
    frames.push({
      at: now,
      rtp: metadata.rtpTimestamp >>> 0,
      time: metadata.expectedDisplayTime,
    });
    while (frames[0].at < now - FRAME_WINDOW_MS) frames.shift();
    frameCallback = video.requestVideoFrameCallback(onVideoFrame);
  }
  if (kind === "video" && video && "requestVideoFrameCallback" in video) {
    frameCallback = video.requestVideoFrameCallback(onVideoFrame);
  }

  function sample() {
    // A closed connection plays nothing more, and the script that made the
    // clock may never close it.
    if (pc.signalingState === "closed") {
      stop();
      return;
    }
    const now = performance.now();
    for (const receiver of pc.getReceivers()) {
      if (receiver.track.kind !== kind) continue;
      const [source] = receiver.getSynchronizationSources();
      if (!source || source.rtpTimestamp === undefined) continue;
      clockRate ??=
        receiver.getParameters().codecs?.[0]?.clockRate ??
        DEFAULT_CLOCK_RATES[kind];
      // `timestamp` is when the receiver last handed media to its track, on
      // performance.timeOrigin + performance.now(), and `rtpTimestamp` is that
      // media's. https://w3c.github.io/webrtc-pc/#dom-rtcrtpcontributingsource-timestamp
      const time = source.timestamp - performance.timeOrigin;
      // The spec keeps sources for 10 s. Anything outside that is on another
      // clock, and a wrong time is worse than none.
      if (time > now + 1000 || time < now - 10000) break;
      const last = estimates[estimates.length - 1];
      if (!last || last.rtp !== source.rtpTimestamp || last.time !== time) {
        estimates.push({ at: now, rtp: source.rtpTimestamp, time });
      }
      break;
    }
    while (estimates.length && estimates[0].at < now - WINDOW_MS) {
      estimates.shift();
    }
  }

  // Audio handed to the track still passes the output device's buffers
  // before it is heard. Browsers that report it do so as the average
  // playout delay of the samples played.
  // https://w3c.github.io/webrtc-stats/#dom-rtcaudioplayoutstats-totalplayoutdelay
  async function sampleOutputDelay() {
    if (kind !== "audio" || pc.signalingState === "closed") return;
    const stats = await pc.getStats();
    stats.forEach((report) => {
      if (report.type !== "media-playout") return;
      const current = {
        delay: report.totalPlayoutDelay,
        samples: report.totalSamplesCount,
      };
      if (previousPlayout && current.samples > previousPlayout.samples) {
        outputDelayMs =
          (1000 * (current.delay - previousPlayout.delay)) /
          (current.samples - previousPlayout.samples);
      }
      previousPlayout = current;
    });
  }

  const timer = setInterval(sample, SAMPLE_INTERVAL_MS);
  const statsTimer = setInterval(sampleOutputDelay, STATS_INTERVAL_MS);

  function playoutTime(rtpTimestamp: number): number | null {
    // sample() refills the estimates for as long as the connection is open,
    // so a clock closed before its connection would keep answering.
    if (closed) return null;
    sample();
    const msPerTick = 1000 / (clockRate ?? DEFAULT_CLOCK_RATES[kind]);
    const now = performance.now();
    const latestFrame = frames[frames.length - 1];
    // The element presents no frames while it is hidden or paused, and the
    // receiver's estimates are then all there is.
    if (latestFrame && latestFrame.at >= now - RECENT_FRAMES_MS) {
      const target = rtpTimestamp >>> 0;
      for (let i = frames.length - 1; i >= 0; i--) {
        if (frames[i].rtp === target) return frames[i].time;
      }
      // A frame not presented yet is due no earlier than the recent frames
      // imply. Some of them waited an extra display refresh, so the earliest
      // of them is the best guess.
      return extrapolate(
        frames.filter((f) => f.at >= now - RECENT_FRAMES_MS),
        target,
        msPerTick,
      );
    }
    if (!estimates.length || clockRate === null) return null;
    return (
      extrapolate(estimates, rtpTimestamp, msPerTick) + (outputDelayMs ?? 0)
    );
  }

  return { playoutTime, close: stop };
}
