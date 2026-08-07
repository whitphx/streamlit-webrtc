import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useWebRtc } from ".";

const switchInputDevice = vi.fn<() => Promise<void>>();
vi.mock("./switch-input-device", () => ({
  switchInputDevice: () => switchInputDevice(),
}));
vi.mock("webrtc-adapter", () => ({ default: {} }));

function makeStream(name: string): MediaStream {
  const track = {
    kind: "video",
    enabled: true,
    readyState: "live",
    stop: vi.fn(),
    getSettings: () => ({ deviceId: name }),
  };
  return {
    name,
    getTracks: () => [track],
    getVideoTracks: () => [track],
    getAudioTracks: () => [],
  } as unknown as MediaStream;
}

class FakePeerConnection {
  localDescription = { type: "offer", sdp: "sdp", toJSON: () => ({}) };
  connectionState = "new";
  private senders: Array<{ track: unknown }> = [];
  addEventListener() {}
  addTrack(track: unknown) {
    this.senders.push({ track });
  }
  addTransceiver() {}
  getTransceivers() {
    return [];
  }
  getSenders() {
    return this.senders;
  }
  createOffer() {
    return Promise.resolve(this.localDescription);
  }
  setLocalDescription() {
    return Promise.resolve();
  }
  close() {}
}

function renderWebRtc() {
  return renderHook(() =>
    useWebRtc(
      {
        mode: "SENDONLY",
        desiredPlayingState: undefined,
        sdpAnswerJson: undefined,
        rtcConfiguration: undefined,
        mediaStreamConstraints: { video: true, audio: false },
        sendbackVideo: false,
        sendbackAudio: false,
      },
      undefined,
      undefined,
      vi.fn(),
      vi.fn(),
      vi.fn(),
    ),
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
  vi.resetAllMocks();
});

describe("useWebRtc", () => {
  it("rejects device switching without an active input stream", async () => {
    const { result } = renderWebRtc();

    await expect(
      result.current.updateInputDevice("video", "next-video"),
    ).rejects.toThrow(
      "Cannot switch input device without an active WebRTC input stream",
    );
  });

  describe("when a switch outlives the stream it was made against", () => {
    const getUserMedia = vi.fn<() => Promise<MediaStream>>();

    beforeEach(() => {
      vi.stubGlobal("navigator", { mediaDevices: { getUserMedia } });
      vi.stubGlobal("RTCPeerConnection", FakePeerConnection);
    });

    it("leaves the stream that replaced it in place", async () => {
      const first = makeStream("first");
      const second = makeStream("second");
      getUserMedia.mockResolvedValueOnce(first).mockResolvedValueOnce(second);
      let finishSwitch: (() => void) | undefined;
      switchInputDevice.mockReturnValue(
        new Promise<void>((resolve) => {
          finishSwitch = resolve;
        }),
      );

      const { result } = renderWebRtc();
      await act(async () => result.current.start());
      expect(result.current.state.inputMediaStream).toBe(first);

      const switching = result.current
        .updateInputDevice("video", "next-video")
        .catch(() => undefined);

      // `getUserMedia` can sit on a permission prompt long enough for the
      // connection to be stopped and started again underneath the switch.
      vi.useFakeTimers();
      await act(async () => {
        result.current.stop();
        await vi.advanceTimersByTimeAsync(1000);
      });
      vi.useRealTimers();
      await act(async () => result.current.start());
      expect(result.current.state.inputMediaStream).toBe(second);

      await act(async () => {
        finishSwitch?.();
        await switching;
      });

      // Publishing the stream the switch was made against would put a stopped
      // one back in place of the one now playing.
      expect(result.current.state.inputMediaStream).toBe(second);
    });
  });
});
