import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createPlayoutClock } from "./playout-clock";

function fakePeerConnection() {
  const source: { current?: { timestamp: number; rtpTimestamp: number } } = {};
  const receiver = {
    track: { kind: "audio" },
    getSynchronizationSources: () => (source.current ? [source.current] : []),
    getParameters: () => ({
      codecs: [{ clockRate: 48000 }],
    }),
  };
  const playout = { totalPlayoutDelay: 0, totalSamplesCount: 0 };
  const pc = {
    signalingState: "stable",
    getReceivers: () => [receiver],
    getStats: async () =>
      new Map([["playout", { type: "media-playout", ...playout }]]),
  } as unknown as RTCPeerConnection;
  // Delivers RTP timestamp `rtp` to playout at page time `at`.
  const deliver = (at: number, rtp: number) => {
    vi.advanceTimersByTime(at - performance.now());
    source.current = {
      timestamp: performance.timeOrigin + at,
      rtpTimestamp: rtp >>> 0,
    };
  };
  return { pc, deliver, playout };
}

describe("createPlayoutClock", () => {
  beforeEach(() => {
    vi.useFakeTimers({
      toFake: ["setInterval", "clearInterval", "performance"],
    });
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns null before the receiver has played anything", () => {
    const { pc } = fakePeerConnection();
    expect(createPlayoutClock(pc, "audio").playoutTime(1234)).toBeNull();
  });

  it("maps an RTP timestamp from the first delivery of each packet", () => {
    const { pc, deliver } = fakePeerConnection();
    const clock = createPlayoutClock(pc, "audio");
    // 20 ms packets played as two 10 ms frames: the second frame of each
    // packet reports the packet's timestamp 10 ms after it started playing.
    deliver(1000, 960);
    deliver(1010, 960);
    deliver(1020, 1920);
    deliver(1030, 1920);

    expect(clock.playoutTime(1920 + 4800)).toBeCloseTo(1020 + 100);
  });

  it("follows RTP timestamps across the 32-bit wrap", () => {
    const { pc, deliver } = fakePeerConnection();
    const clock = createPlayoutClock(pc, "audio");
    deliver(5000, 2 ** 32 - 960);
    deliver(5020, 0);

    expect(clock.playoutTime(960)).toBeCloseTo(5040);
    expect(clock.playoutTime(2 ** 32 - 1920)).toBeCloseTo(4980);
  });

  it("adds the output delay that the playout stats report", async () => {
    const { pc, deliver, playout } = fakePeerConnection();
    const clock = createPlayoutClock(pc, "audio");
    await vi.advanceTimersByTimeAsync(1000);
    // A second of audio played 30 ms after the receiver handed it over.
    playout.totalSamplesCount = 48000;
    playout.totalPlayoutDelay = 48000 * 0.03;
    await vi.advanceTimersByTimeAsync(1000);
    deliver(2010, 960);
    deliver(2020, 1920);

    expect(clock.playoutTime(1920)).toBeCloseTo(2020 + 30);
  });

  it("ignores a timestamp that is not on the page's clock", () => {
    const { pc } = fakePeerConnection();
    const receiver = pc.getReceivers()[0];
    receiver.getSynchronizationSources = () => [
      { timestamp: Date.now() + 3_600_000, rtpTimestamp: 0, source: 1 },
    ];

    expect(createPlayoutClock(pc, "audio").playoutTime(0)).toBeNull();
  });
});
