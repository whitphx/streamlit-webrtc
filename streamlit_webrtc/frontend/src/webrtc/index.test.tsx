import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useWebRtc, type DataChannelSpec } from ".";

const switchInputDevice = vi.fn<() => Promise<void>>();
vi.mock("./switch-input-device", () => ({
  switchInputDevice: () => switchInputDevice(),
}));
vi.mock("webrtc-adapter", () => ({ default: {} }));
const frontendScriptSetup = vi.fn();
vi.mock("./frontend-script", () => ({
  loadFrontendScript: () => Promise.resolve(frontendScriptSetup),
}));

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
  dataChannels: Array<{ label: string; init: RTCDataChannelInit }> = [];
  offerCreated = false;
  addEventListener() {}
  createDataChannel(label: string, init: RTCDataChannelInit) {
    if (this.offerCreated) {
      throw new Error("Created after the offer");
    }
    this.dataChannels.push({ label, init });
    return { label };
  }
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
    this.offerCreated = true;
    return Promise.resolve(this.localDescription);
  }
  setLocalDescription() {
    return Promise.resolve();
  }
  close() {}
}

function renderWebRtc(
  extraProps: {
    dataChannels?: DataChannelSpec[];
    frontendScript?: string;
    frontendScriptRoot?: HTMLDivElement;
  } = {},
) {
  return renderHook(() =>
    useWebRtc(
      {
        ...extraProps,
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

  describe("with data channels and a frontend script", () => {
    beforeEach(() => {
      vi.stubGlobal("navigator", {
        mediaDevices: {
          getUserMedia: () => Promise.resolve(makeStream("camera")),
        },
      });
      vi.stubGlobal("RTCPeerConnection", FakePeerConnection);
    });

    it("negotiates the channels and runs the script for the session", async () => {
      const cleanup = vi.fn();
      frontendScriptSetup.mockImplementation(({ root }) => {
        root.appendChild(document.createElement("canvas"));
        return cleanup;
      });
      const root = document.createElement("div");

      const { result } = renderWebRtc({
        dataChannels: [
          { label: "events", id: 0 },
          { label: "frames", id: 1, ordered: false, maxRetransmits: 0 },
        ],
        frontendScript: "export default () => {}",
        frontendScriptRoot: root,
      });
      await act(async () => result.current.start());

      const [{ pc, channels, root: scriptRoot }] =
        frontendScriptSetup.mock.calls[0];
      expect((pc as FakePeerConnection).dataChannels).toEqual([
        { label: "events", init: { id: 0, negotiated: true } },
        {
          label: "frames",
          init: { id: 1, ordered: false, maxRetransmits: 0, negotiated: true },
        },
      ]);
      expect(Object.keys(channels)).toEqual(["events", "frames"]);
      expect(scriptRoot).toBe(root);
      expect(root.childElementCount).toBe(1);

      vi.useFakeTimers();
      await act(async () => {
        result.current.stop();
        await vi.advanceTimersByTimeAsync(1000);
      });

      expect(cleanup).toHaveBeenCalledOnce();
      expect(root.childElementCount).toBe(0);
    });

    it("fails the start when the script throws", async () => {
      frontendScriptSetup.mockRejectedValue(new Error("script bug"));

      const { result } = renderWebRtc({
        frontendScript: "export default () => {}",
        frontendScriptRoot: document.createElement("div"),
      });
      await act(async () => result.current.start());

      expect(result.current.state.webRtcState).toBe("STOPPED");
      expect(result.current.state.error?.message).toBe("script bug");
    });
  });
});
