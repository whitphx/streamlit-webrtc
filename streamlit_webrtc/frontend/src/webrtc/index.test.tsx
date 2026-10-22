import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useWebRtc, type DataChannelSpec } from ".";
import {
  FrontendScriptError,
  type FrontendScriptMedia,
} from "./frontend-script";

const switchInputDevice = vi.fn<() => Promise<void>>();
vi.mock("./switch-input-device", () => ({
  switchInputDevice: () => switchInputDevice(),
}));
vi.mock("webrtc-adapter", () => ({ default: {} }));
const frontendScriptSetup = vi.fn();
let frontendScriptLoaded: Promise<void> = Promise.resolve();
vi.mock("./frontend-script", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./frontend-script")>()),
  loadFrontendScript: () =>
    frontendScriptLoaded.then(() => frontendScriptSetup),
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
  closed = false;
  addEventListener() {}
  createDataChannel(label: string, init: RTCDataChannelInit) {
    if (this.offerCreated) {
      throw new Error("Created after the offer");
    }
    // Mirrors the `[EnforceRange] unsigned short` conversion in browsers.
    if ((init.maxRetransmits ?? 0) > 65535) {
      throw new TypeError("maxRetransmits is out of range");
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
  close() {
    this.closed = true;
  }
}

interface ExtraProps {
  dataChannels?: DataChannelSpec[];
  frontendScript?: string;
  frontendData?: unknown;
  frontendScriptRootRef?: { current: HTMLDivElement | null };
  frontendScriptMediaRef?: { current: FrontendScriptMedia };
}

function renderWebRtc(initialProps: ExtraProps = {}) {
  return renderHook(
    (extraProps: ExtraProps) =>
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
    { initialProps },
  );
}

afterEach(() => {
  frontendScriptLoaded = Promise.resolve();
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

  describe("when the offer settles after a stop", () => {
    let settleOffer:
      { resolve: () => void; reject: (error: Error) => void } | undefined;

    beforeEach(() => {
      settleOffer = undefined;
      vi.stubGlobal("navigator", {
        mediaDevices: {
          getUserMedia: () => Promise.resolve(makeStream("camera")),
        },
      });
      vi.stubGlobal(
        "RTCPeerConnection",
        class extends FakePeerConnection {
          setLocalDescription() {
            return new Promise<void>((resolve, reject) => {
              settleOffer = { resolve, reject };
            });
          }
        },
      );
    });

    it.each([
      ["succeeds", () => settleOffer?.resolve()],
      ["fails", () => settleOffer?.reject(new Error("closed"))],
    ])("ignores an offer that %s", async (_, settle) => {
      const { result } = renderWebRtc();
      await act(async () => result.current.start());
      expect(settleOffer).toBeDefined();

      vi.useFakeTimers();
      await act(async () => {
        result.current.stop();
        await vi.advanceTimersByTimeAsync(1000);
      });
      vi.useRealTimers();
      await act(async () => settle());

      expect(result.current.state.webRtcState).toBe("STOPPED");
      expect(result.current.state.sdpOffer).toBeNull();
      expect(result.current.state.error).toBeNull();
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
      const video = document.createElement("video");

      const { result } = renderWebRtc({
        dataChannels: [
          { label: "events", id: 0 },
          { label: "frames", id: 1, ordered: false, maxRetransmits: 0 },
        ],
        frontendScript: "export default () => {}",
        frontendData: { color: "red" },
        frontendScriptRootRef: { current: root },
        frontendScriptMediaRef: { current: { video } },
      });
      await act(async () => result.current.start());

      expect(frontendScriptSetup).toHaveBeenCalledOnce();
      const [{ pc, channels, root: scriptRoot, media, data }] =
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
      expect(media).toEqual({ video });
      expect(data).toEqual({ color: "red" });
      expect(root.childElementCount).toBe(1);

      vi.useFakeTimers();
      await act(async () => {
        result.current.stop();
        await vi.advanceTimersByTimeAsync(1000);
      });

      expect(cleanup).toHaveBeenCalledOnce();
      expect(root.childElementCount).toBe(0);
    });

    it("calls the script's update only when the data changes", async () => {
      const update = vi.fn();
      const cleanup = vi.fn();
      frontendScriptSetup.mockReturnValue({ update, cleanup });
      const props = {
        frontendScript: "export default () => {}",
        frontendData: { color: "red", threshold: 1 },
        frontendScriptRootRef: { current: document.createElement("div") },
      };

      const { result, rerender } = renderWebRtc(props);
      await act(async () => result.current.start());

      rerender({ ...props, frontendData: { threshold: 1, color: "red" } });
      expect(update).not.toHaveBeenCalled();

      rerender({ ...props, frontendData: { color: "blue", threshold: 1 } });
      rerender({ ...props, frontendData: { color: "blue", threshold: 1 } });
      expect(update).toHaveBeenCalledOnce();
      expect(update).toHaveBeenCalledWith({ color: "blue", threshold: 1 });
      expect(frontendScriptSetup).toHaveBeenCalledOnce();

      vi.useFakeTimers();
      await act(async () => {
        result.current.stop();
        await vi.advanceTimersByTimeAsync(1000);
      });
      expect(cleanup).toHaveBeenCalledOnce();
    });

    it("delivers data that changed while the setup was running", async () => {
      const update = vi.fn();
      let finishSetup = () => {};
      frontendScriptSetup.mockReturnValue(
        new Promise((resolve) => {
          finishSetup = () => resolve({ update });
        }),
      );
      const props = {
        frontendScript: "export default () => {}",
        frontendData: 1,
        frontendScriptRootRef: { current: document.createElement("div") },
      };

      const { result, rerender } = renderWebRtc(props);
      let started: Promise<void> = Promise.resolve();
      await act(async () => {
        started = result.current.start();
      });
      rerender({ ...props, frontendData: 2 });
      await act(async () => {
        finishSetup();
        await started;
      });

      expect(update).toHaveBeenCalledExactlyOnceWith(2);
    });

    it("ignores data changes when the script has no update", async () => {
      frontendScriptSetup.mockReturnValue(undefined);
      const props = {
        frontendScript: "export default () => {}",
        frontendData: 1,
        frontendScriptRootRef: { current: document.createElement("div") },
      };

      const { result, rerender } = renderWebRtc(props);
      await act(async () => result.current.start());
      rerender({ ...props, frontendData: 2 });

      expect(result.current.state.error).toBeNull();
      expect(frontendScriptSetup).toHaveBeenCalledOnce();
    });

    it("tears down a session that was stopped during the script's setup", async () => {
      const cleanup = vi.fn();
      let finishSetup = () => {};
      frontendScriptSetup.mockReturnValue(
        new Promise((resolve) => {
          finishSetup = () => resolve(cleanup);
        }),
      );
      const root = document.createElement("div");
      root.appendChild(document.createElement("canvas"));

      const { result } = renderWebRtc({
        frontendScript: "export default () => {}",
        frontendScriptRootRef: { current: root },
      });
      let started: Promise<void> = Promise.resolve();
      await act(async () => {
        started = result.current.start();
      });
      expect(result.current.state.webRtcState).toBe("SIGNALLING");

      await act(async () => result.current.stop());
      expect(result.current.state.webRtcState).toBe("STOPPED");

      await act(async () => {
        finishSetup();
        await started;
      });

      const [{ pc }] = frontendScriptSetup.mock.calls[0];
      const fakePc = pc as FakePeerConnection;
      expect(fakePc.offerCreated).toBe(false);
      expect(fakePc.closed).toBe(true);
      for (const sender of fakePc.getSenders()) {
        expect((sender.track as MediaStreamTrack).stop).toHaveBeenCalled();
      }
      expect(cleanup).toHaveBeenCalledOnce();
      expect(root.childElementCount).toBe(0);
      expect(result.current.state.webRtcState).toBe("STOPPED");
      expect(result.current.state.sdpOffer).toBeNull();
      expect(result.current.state.error).toBeNull();
    });

    it("releases the camera and the connection on stop while the setup is still running", async () => {
      let finishLoading = () => {};
      const loading = new Promise<void>((resolve) => {
        finishLoading = resolve;
      });
      frontendScriptSetup.mockImplementation(async ({ root }) => {
        root.appendChild(document.createElement("canvas"));
        await loading;
        root.appendChild(document.createElement("canvas"));
      });
      const root = document.createElement("div");

      const { result } = renderWebRtc({
        frontendScript: "export default () => {}",
        frontendScriptRootRef: { current: root },
      });
      let started: Promise<void> = Promise.resolve();
      await act(async () => {
        started = result.current.start();
      });
      expect(frontendScriptSetup).toHaveBeenCalledOnce();

      await act(async () => result.current.stop());

      const [{ pc }] = frontendScriptSetup.mock.calls[0];
      const fakePc = pc as FakePeerConnection;
      expect(fakePc.closed).toBe(true);
      expect(fakePc.getSenders()).not.toHaveLength(0);
      for (const sender of fakePc.getSenders()) {
        expect((sender.track as MediaStreamTrack).stop).toHaveBeenCalled();
      }
      expect(root.childElementCount).toBe(0);
      expect(result.current.state.webRtcState).toBe("STOPPED");

      await act(async () => {
        finishLoading();
        await started;
      });

      expect(root.childElementCount).toBe(0);
      expect(fakePc.offerCreated).toBe(false);
      expect(result.current.state.webRtcState).toBe("STOPPED");
    });

    it("refuses a second start while the script is loading", async () => {
      const PeerConnection = vi.fn(function () {
        return new FakePeerConnection();
      });
      vi.stubGlobal("RTCPeerConnection", PeerConnection);
      let finishLoad = () => {};
      frontendScriptLoaded = new Promise((resolve) => {
        finishLoad = resolve;
      });
      const props = {
        frontendScript: "export default () => {}",
        frontendScriptRootRef: { current: document.createElement("div") },
      };

      const { result } = renderWebRtc(props);
      let started: Promise<void> = Promise.resolve();
      await act(async () => {
        started = result.current.start();
      });
      await expect(result.current.start()).rejects.toThrow(
        "WebRTC is already started",
      );

      await act(async () => {
        finishLoad();
        await started;
      });

      expect(PeerConnection).toHaveBeenCalledOnce();
      expect(frontendScriptSetup).toHaveBeenCalledOnce();
      expect(result.current.state.sdpOffer).not.toBeNull();
    });

    it("leaves the next session's root alone when a stopped setup finishes", async () => {
      const staleCleanup = vi.fn();
      let finishStaleSetup = () => {};
      frontendScriptSetup
        .mockImplementationOnce(({ root }) => {
          root.appendChild(document.createElement("canvas"));
          return new Promise((resolve) => {
            finishStaleSetup = () => resolve(staleCleanup);
          });
        })
        .mockImplementationOnce(({ root }) => {
          root.appendChild(document.createElement("canvas"));
        });
      const root = document.createElement("div");

      const { result } = renderWebRtc({
        frontendScript: "export default () => {}",
        frontendScriptRootRef: { current: root },
      });
      let staleStarted: Promise<void> = Promise.resolve();
      await act(async () => {
        staleStarted = result.current.start();
      });
      await act(async () => result.current.stop());
      await act(async () => result.current.start());
      expect(root.childElementCount).toBe(1);

      await act(async () => {
        finishStaleSetup();
        await staleStarted;
      });

      const [{ pc: stalePc }] = frontendScriptSetup.mock.calls[0];
      expect((stalePc as FakePeerConnection).closed).toBe(true);
      expect(staleCleanup).toHaveBeenCalledOnce();
      expect(root.childElementCount).toBe(1);
      expect(result.current.state.webRtcState).toBe("SIGNALLING");
      expect(result.current.state.sdpOffer).not.toBeNull();
    });

    it("releases the camera and the connection when the setup throws", async () => {
      const camera = makeStream("camera");
      vi.stubGlobal("navigator", {
        mediaDevices: { getUserMedia: () => Promise.resolve(camera) },
      });
      const pcs: FakePeerConnection[] = [];
      vi.stubGlobal(
        "RTCPeerConnection",
        vi.fn(function () {
          const pc = new FakePeerConnection();
          pcs.push(pc);
          return pc;
        }),
      );

      const { result } = renderWebRtc({
        dataChannels: [{ label: "frames", id: 0, maxRetransmits: 65536 }],
      });
      await act(async () => result.current.start());

      expect(result.current.state.webRtcState).toBe("STOPPED");
      expect(result.current.state.error).toBeInstanceOf(TypeError);
      expect(pcs).toHaveLength(1);
      expect(pcs[0].closed).toBe(true);
      for (const track of camera.getTracks()) {
        expect(track.stop).toHaveBeenCalled();
      }
    });

    it("fails the start when the script throws", async () => {
      vi.spyOn(console, "error").mockImplementation(() => {});
      frontendScriptSetup.mockRejectedValue(new Error("script bug"));

      const { result } = renderWebRtc({
        frontendScript: "export default () => {}",
        frontendScriptRootRef: { current: document.createElement("div") },
      });
      await act(async () => result.current.start());

      expect(result.current.state.webRtcState).toBe("STOPPED");
      expect(result.current.state.error).toBeInstanceOf(FrontendScriptError);
      expect(result.current.state.error?.message).toBe("script bug");
    });
  });
});
