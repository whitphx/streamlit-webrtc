// A receiver reports one RTP timestamp per packet, while it hands media to
// playout in smaller pieces: a 20 ms Opus packet goes out as two 10 ms frames
// with the same timestamp. Only the earliest delivery seen for a packet
// marks when its first sample played, so the clock keeps the earliest
// estimate over a window several packets long.
const WINDOW_MS = 300;
const SAMPLE_INTERVAL_MS = 10;
const STATS_INTERVAL_MS = 1000;
const DEFAULT_CLOCK_RATES = { audio: 48000, video: 90000 } as const;

export interface PlayoutClock {
  /** The `performance.now()` time at which the received media with this RTP
   * timestamp is heard or shown, or `null` until the media plays. */
  playoutTime(rtpTimestamp: number): number | null;
  close(): void;
}

function wrapDelta(a: number, b: number): number {
  return ((((a - b) % 2 ** 32) + 2 ** 32 + 2 ** 31) % 2 ** 32) - 2 ** 31;
}

export function createPlayoutClock(
  pc: RTCPeerConnection,
  kind: "audio" | "video",
): PlayoutClock {
  // Each estimate is the time the receiver handed RTP timestamp `rtp` to its track.
  let estimates: { at: number; rtp: number; time: number }[] = [];
  let clockRate: number | null = null;
  let outputDelayMs: number | null = null;
  let previousPlayout: { delay: number; samples: number } | null = null;

  function stop() {
    clearInterval(timer);
    clearInterval(statsTimer);
    estimates = [];
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
    sample();
    const latest = estimates[estimates.length - 1];
    if (!latest || clockRate === null) return null;
    const msPerTick = 1000 / clockRate;
    let earliest = Infinity;
    for (const e of estimates) {
      earliest = Math.min(
        earliest,
        e.time - wrapDelta(e.rtp, latest.rtp) * msPerTick,
      );
    }
    return (
      earliest +
      wrapDelta(rtpTimestamp, latest.rtp) * msPerTick +
      (outputDelayMs ?? 0)
    );
  }

  return { playoutTime, close: stop };
}
