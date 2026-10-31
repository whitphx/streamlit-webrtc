import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createPlayoutClock } from "./playout-clock";

function fakePeerConnection(kind: "audio" | "video" = "audio") {
  const source: { current?: { timestamp: number; rtpTimestamp: number } } = {};
  const receiver = {
    track: { kind },
    getSynchronizationSources: () => (source.current ? [source.current] : []),
    getParameters: () => ({
      codecs: [{ clockRate: kind === "audio" ? 48000 : 90000 }],
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

// A video element that presents a frame when the test says so.
function fakeVideo({ rtpTimestamps = true } = {}) {
  let callbacks = new Map<number, VideoFrameRequestCallback>();
  let nextHandle = 1;
  const video = {
    requestVideoFrameCallback(callback: VideoFrameRequestCallback) {
      callbacks.set(nextHandle, callback);
      return nextHandle++;
    },
    cancelVideoFrameCallback(handle: number) {
      callbacks.delete(handle);
    },
  } as unknown as HTMLVideoElement;
  // Presents the frame with RTP timestamp `rtp` at page time `at`, to be
  // visible at `displayAt`.
  const present = (at: number, rtp: number, displayAt = at + 16) => {
    vi.advanceTimersByTime(at - performance.now());
    const pending = callbacks;
    callbacks = new Map();
    for (const callback of pending.values()) {
      callback(at, {
        expectedDisplayTime: displayAt,
        presentationTime: at,
        ...(rtpTimestamps && { rtpTimestamp: rtp >>> 0 }),
      } as VideoFrameCallbackMetadata);
    }
  };
  return { video, present, pendingCallbacks: () => callbacks.size };
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

  describe("video", () => {
    it("gives the time the element shows a presented frame", () => {
      const { pc } = fakePeerConnection("video");
      const { video, present } = fakeVideo();
      const clock = createPlayoutClock(pc, "video", video);
      present(1000, 3000, 1016);
      present(1033, 6000, 1050);
      present(1066, 9000, 1083);

      expect(clock.playoutTime(6000)).toBe(1050);
    });

    it("places a frame not presented yet on the earliest recent timeline", () => {
      const { pc } = fakePeerConnection("video");
      const { video, present } = fakeVideo();
      const clock = createPlayoutClock(pc, "video", video);
      // 30 fps on a 60 Hz display: the middle frame waited a refresh.
      present(1000, 3000, 1016);
      present(1050, 6000, 1066);
      present(1066, 9000, 1083);

      expect(clock.playoutTime(12000)).toBeCloseTo(1016 + 100);
    });

    it("falls back to the receiver where frames carry no RTP timestamp", () => {
      const { pc, deliver } = fakePeerConnection("video");
      const { video, present, pendingCallbacks } = fakeVideo({
        rtpTimestamps: false,
      });
      const clock = createPlayoutClock(pc, "video", video);
      present(1000, 3000);
      deliver(1010, 3000);

      expect(pendingCallbacks()).toBe(0);
      expect(clock.playoutTime(6000)).toBeCloseTo(1010 + 1000 / 30);
    });

    it("falls back to the receiver while the element presents nothing", () => {
      const { pc, deliver } = fakePeerConnection("video");
      const { video, present } = fakeVideo();
      const clock = createPlayoutClock(pc, "video", video);
      present(1000, 3000, 1016);
      deliver(3000, 63000);

      expect(clock.playoutTime(66000)).toBeCloseTo(3000 + 1000 / 30);
    });

    it("works without requestVideoFrameCallback", () => {
      const { pc, deliver } = fakePeerConnection("video");
      const clock = createPlayoutClock(pc, "video", {} as HTMLVideoElement);
      deliver(1000, 3000);

      expect(clock.playoutTime(3000)).toBeCloseTo(1000);
    });

    it("stops watching the element when closed", () => {
      const { pc } = fakePeerConnection("video");
      const { video, present, pendingCallbacks } = fakeVideo();
      const clock = createPlayoutClock(pc, "video", video);
      present(1000, 3000);
      clock.close();

      expect(pendingCallbacks()).toBe(0);
      expect(clock.playoutTime(3000)).toBeNull();
    });
  });
});
