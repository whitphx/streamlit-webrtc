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
const STATS_INTERVAL_MS = 250;
const DEFAULT_CLOCK_RATES = { audio: 48000, video: 90000 } as const;

// Margins are judged per second, and the buffer only moves on what most
// recent seconds agree on. A sender that stalls delivers one burst of very
// late data and then catches up; delaying the media for every stall would
// keep it at the cap without saving the frames of the next one.
const BUCKET_MS = 1000;
// A second with only a few arrivals is the tail of a stall, not a second the
// data kept its usual pace through.
const MIN_BUCKET_SAMPLES = 10;
const RAISE_BUCKETS = 5;
const MARGIN_WINDOW_MS = 8000;
// The jitter buffer grows gradually, by stretching audio or holding frames,
// so a raise takes a while to show in the margins.
// Raising again before then would count the same shortfall twice.
const SETTLE_MS = 1500;
const LATE_QUANTILE = 0.98;
// Lowering runs on margins seconds old, so it overshoots by its rate times
// the few seconds the raise takes to notice. At this rate the overshoot stays
// within a typical safety margin, so frames come close but not late.
const LOWER_MS_PER_S = 10;
// Data arriving right after the channel opens or after a gap is late for
// reasons that pass on their own: the transport has no RTT estimate yet, or
// the sender is flushing what piled up while it stalled. Holding the media
// back for those seconds delays everything after them for nothing.
const START_GRACE_MS = 3000;
const ARRIVAL_GAP_MS = 500;
const GAP_GRACE_MS = 2000;

export interface HoldForDataOptions {
  /** Margin in ms that data should keep ahead of its media's playout, e.g.
   * the time needed to render it. */
  safetyMs?: number;
  /** The most the media may be delayed, in ms. */
  maxMs?: number;
}

export interface PlayoutClockOptions {
  /** Delay the media through the receiver's `jitterBufferTarget` when the
   * data reported with `noteDataArrival()` arrives too late for it. */
  holdForData?: HoldForDataOptions;
}

export interface HoldState {
  /** Whether the clock adjusts the receiver: `holdForData` was given and the
   * browser has `jitterBufferTarget`. */
  supported: boolean;
  targetMs: number | null;
  jitterBufferMs: number | null;
  /** The margin, in ms, that nearly all recent data kept, taken over the
   * median second. */
  marginMs: number | null;
}

export interface PlayoutClock {
  /** The `performance.now()` time at which the received media with this RTP
   * timestamp is heard or shown, or `null` until the media plays. */
  playoutTime(rtpTimestamp: number): number | null;
  /** Reports that the data for this RTP timestamp has arrived. `holdForData`
   * is judged by these arrivals, and `hold().marginMs` reports their margin. */
  noteDataArrival(rtpTimestamp: number, arrivalTime?: number): void;
  hold(): HoldState;
  /** Stops the clock and releases any hold it put on the receiver. */
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

function lowQuantile(xs: number[]): number | null {
  if (!xs.length) return null;
  const sorted = [...xs].sort((a, b) => a - b);
  return sorted[Math.floor((sorted.length - 1) * (1 - LATE_QUANTILE))];
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

// The upper median, so that late seconds have to be the majority.
function median(xs: number[]): number | null {
  if (!xs.length) return null;
  const sorted = [...xs].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
}

// The low quantile of the margins in each whole BUCKET_MS from `since` to
// `now`, skipping sparse buckets.
function bucketLows(
  margins: { at: number; margin: number }[],
  since: number,
  now: number,
): number[] {
  const lows: number[] = [];
  for (let end = now; end - BUCKET_MS >= since; end -= BUCKET_MS) {
    const bucket = margins
      .filter((m) => m.at >= end - BUCKET_MS && m.at < end)
      .map((m) => m.margin);
    if (bucket.length < MIN_BUCKET_SAMPLES) continue;
    const low = lowQuantile(bucket);
    if (low !== null) lows.push(low);
  }
  return lows;
}

export function createPlayoutClock(
  pc: RTCPeerConnection,
  kind: "audio" | "video",
  { holdForData }: PlayoutClockOptions = {},
  video?: HTMLVideoElement,
): PlayoutClock {
  // Each estimate is the time the receiver handed RTP timestamp `rtp` to its track.
  let estimates: Estimate[] = [];
  // Each frame is the time the video element showed RTP timestamp `rtp`.
  let frames: Estimate[] = [];
  let clockRate: number | null = null;
  let outputDelayMs: number | null = null;
  let jitterBufferMs: number | null = null;
  const previous: {
    playout?: { delay: number; samples: number };
    inbound?: { delay: number; emitted: number };
  } = {};
  let margins: { at: number; margin: number }[] = [];
  let targetMs: number | null = null;
  let lastRaise = -Infinity;
  let lastControl: number | null = null;
  let lastArrival: number | null = null;
  let ignoreUntil = -Infinity;
  const safetyMs = holdForData?.safetyMs ?? 40;
  const maxMs = holdForData?.maxMs ?? 400;

  // jitterBufferTarget is a hint the receiver may not follow, and older
  // browsers lack it. https://w3c.github.io/webrtc-pc/#dom-rtcrtpreceiver-jitterbuffertarget
  const supported =
    holdForData !== undefined &&
    typeof RTCRtpReceiver !== "undefined" &&
    "jitterBufferTarget" in RTCRtpReceiver.prototype;

  function setTarget(ms: number | null) {
    const receiver = pc.getReceivers().find((r) => r.track.kind === kind);
    if (!receiver) return;
    targetMs = ms;
    try {
      receiver.jitterBufferTarget = ms === null ? null : Math.round(ms);
    } catch (error) {
      console.warn("jitterBufferTarget rejected", error);
    }
  }

  function stop() {
    clearInterval(timer);
    clearInterval(statsTimer);
    if (frameCallback !== null) video?.cancelVideoFrameCallback(frameCallback);
    frameCallback = null;
    estimates = [];
    frames = [];
    margins = [];
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

  async function sampleStats() {
    if (pc.signalingState === "closed") return;
    const stats = await pc.getStats();
    stats.forEach((report) => {
      // Audio handed to the track still passes the output device's buffers
      // before it is heard. Browsers that report it do so as the average
      // playout delay of the samples played.
      // https://w3c.github.io/webrtc-stats/#dom-rtcaudioplayoutstats-totalplayoutdelay
      if (report.type === "media-playout" && kind === "audio") {
        const current = {
          delay: report.totalPlayoutDelay,
          samples: report.totalSamplesCount,
        };
        const before = previous.playout;
        if (before && current.samples > before.samples) {
          outputDelayMs =
            (1000 * (current.delay - before.delay)) /
            (current.samples - before.samples);
        }
        previous.playout = current;
      }
      if (report.type === "inbound-rtp" && report.kind === kind) {
        const current = {
          delay: report.jitterBufferDelay,
          emitted: report.jitterBufferEmittedCount,
        };
        const before = previous.inbound;
        if (before && current.emitted > before.emitted) {
          jitterBufferMs =
            (1000 * (current.delay - before.delay)) /
            (current.emitted - before.emitted);
        }
        previous.inbound = current;
      }
    });
    if (supported) control(performance.now());
  }

  // The margins come from the playout clock, so they show what the buffer
  // actually does rather than what the target asked for: when the receiver
  // ignores a target, the data stays late and the next raise asks for more.
  function control(now: number) {
    while (margins.length && margins[0].at < now - MARGIN_WINDOW_MS) {
      margins.shift();
    }
    const dt = lastControl === null ? 0 : now - lastControl;
    lastControl = now;
    // Without the buffer's own delay, a raise could not tell how much of the
    // target the buffer already holds.
    if (jitterBufferMs === null) return;
    if (!margins.length) {
      if (targetMs !== null) setTarget(null);
      return;
    }
    const recent = bucketLows(
      margins,
      Math.max(now - RAISE_BUCKETS * BUCKET_MS, lastRaise + SETTLE_MS),
      now,
    );
    // A stall spans at most two seconds, so three late seconds are not one.
    const recentLow = recent.length >= 3 ? median(recent) : null;
    if (recentLow !== null && recentLow < safetyMs) {
      // A target below the delay the buffer already holds changes nothing,
      // so the raise starts from whichever is larger.
      const base = Math.max(targetMs ?? 0, jitterBufferMs);
      // The shortfall is measured against a buffer that may still be growing
      // from the last raise, so one raise covers at most one safety margin.
      setTarget(
        Math.min(maxMs, base + Math.min(safetyMs, safetyMs - recentLow)),
      );
      lastRaise = now;
      return;
    }
    const low = median(bucketLows(margins, now - MARGIN_WINDOW_MS, now));
    if (targetMs !== null && low !== null && low > safetyMs) {
      const lowered =
        targetMs - Math.min(low - safetyMs, (LOWER_MS_PER_S * dt) / 1000);
      setTarget(lowered > 0 ? lowered : null);
    }
  }

  const timer = setInterval(sample, SAMPLE_INTERVAL_MS);
  const statsTimer = setInterval(sampleStats, STATS_INTERVAL_MS);

  function playoutTime(rtpTimestamp: number): number | null {
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

  return {
    playoutTime,
    noteDataArrival(rtpTimestamp, arrivalTime = performance.now()) {
      if (lastArrival === null) {
        ignoreUntil = arrivalTime + START_GRACE_MS;
      } else if (arrivalTime - lastArrival > ARRIVAL_GAP_MS) {
        ignoreUntil = Math.max(ignoreUntil, arrivalTime + GAP_GRACE_MS);
      }
      lastArrival = arrivalTime;
      if (arrivalTime < ignoreUntil) return;
      const due = playoutTime(rtpTimestamp);
      if (due === null) return;
      const margin = due - arrivalTime;
      // No allowed hold saves data this late, and counting it would only pin
      // the target at the cap.
      if (margin < -maxMs) return;
      margins.push({ at: arrivalTime, margin });
      while (margins[0].at < arrivalTime - MARGIN_WINDOW_MS) margins.shift();
    },
    hold: () => ({
      supported,
      targetMs,
      jitterBufferMs,
      marginMs: median(
        bucketLows(
          margins,
          performance.now() - MARGIN_WINDOW_MS,
          performance.now(),
        ),
      ),
    }),
    close() {
      // The receiver outlives the clock, e.g. when a script swaps clocks to
      // change options, and must not keep a hold nobody manages.
      if (targetMs !== null) setTarget(null);
      stop();
    },
  };
}
