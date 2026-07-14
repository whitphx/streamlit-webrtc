import { afterEach, describe, expect, it, vi } from "vitest";
import { switchInputDevice } from "./switch-input-device";

function makeTrack(kind: "video" | "audio", enabled = true) {
  return {
    kind,
    enabled,
    stop: vi.fn(),
  } as unknown as MediaStreamTrack;
}

function makeStream(tracks: MediaStreamTrack[]) {
  return {
    getTracks: () => tracks,
    removeTrack: vi.fn(),
    addTrack: vi.fn(),
  } as unknown as MediaStream;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("switchInputDevice", () => {
  it.each(["video", "audio"] as const)(
    "acquires and replaces only the changed %s track",
    async (kind) => {
      const previousTrack = makeTrack(kind, false);
      const unchangedTrack = makeTrack(kind === "video" ? "audio" : "video");
      const nextTrack = makeTrack(kind);
      const inputMediaStream = makeStream([previousTrack, unchangedTrack]);
      const nextStream = makeStream([nextTrack]);
      const replaceTrack = vi.fn().mockResolvedValue(undefined);
      const getUserMedia = vi.fn().mockResolvedValue(nextStream);
      vi.stubGlobal("navigator", { mediaDevices: { getUserMedia } });

      await switchInputDevice(
        {
          getSenders: () => [
            { track: previousTrack, replaceTrack } as unknown as RTCRtpSender,
          ],
        },
        inputMediaStream,
        { video: true, audio: true },
        kind,
        `${kind}-device`,
      );

      expect(getUserMedia).toHaveBeenCalledWith(
        kind === "video"
          ? {
              video: { deviceId: { exact: "video-device" } },
              audio: false,
            }
          : {
              video: false,
              audio: { deviceId: { exact: "audio-device" } },
            },
      );
      expect(replaceTrack).toHaveBeenCalledWith(nextTrack);
      expect(nextTrack.enabled).toBe(false);
      expect(inputMediaStream.removeTrack).toHaveBeenCalledWith(previousTrack);
      expect(inputMediaStream.addTrack).toHaveBeenCalledWith(nextTrack);
      expect(previousTrack.stop).toHaveBeenCalledOnce();
      expect(unchangedTrack.stop).not.toHaveBeenCalled();
    },
  );

  it("keeps the previous track alive until replacement succeeds", async () => {
    const previousTrack = makeTrack("video");
    const nextTrack = makeTrack("video");
    const inputMediaStream = makeStream([previousTrack]);
    const nextStream = makeStream([nextTrack]);
    let finishReplacement: (() => void) | undefined;
    const replaceTrack = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          finishReplacement = resolve;
        }),
    );
    vi.stubGlobal("navigator", {
      mediaDevices: {
        getUserMedia: vi.fn().mockResolvedValue(nextStream),
      },
    });

    const switching = switchInputDevice(
      {
        getSenders: () => [
          { track: previousTrack, replaceTrack } as unknown as RTCRtpSender,
        ],
      },
      inputMediaStream,
      { video: true, audio: true },
      "video",
      "next-video",
    );
    await vi.waitFor(() => expect(replaceTrack).toHaveBeenCalledOnce());

    expect(previousTrack.stop).not.toHaveBeenCalled();
    finishReplacement?.();
    await switching;
    expect(previousTrack.stop).toHaveBeenCalledOnce();
  });

  it("cleans up the new track and leaves the previous track active on failure", async () => {
    const previousTrack = makeTrack("audio");
    const nextTrack = makeTrack("audio");
    const inputMediaStream = makeStream([previousTrack]);
    const nextStream = makeStream([nextTrack]);
    const error = new DOMException("Device is busy", "NotReadableError");
    vi.stubGlobal("navigator", {
      mediaDevices: {
        getUserMedia: vi.fn().mockResolvedValue(nextStream),
      },
    });

    await expect(
      switchInputDevice(
        {
          getSenders: () => [
            {
              track: previousTrack,
              replaceTrack: vi.fn().mockRejectedValue(error),
            } as unknown as RTCRtpSender,
          ],
        },
        inputMediaStream,
        { video: true, audio: true },
        "audio",
        "busy-audio",
      ),
    ).rejects.toBe(error);

    expect(nextTrack.stop).toHaveBeenCalledOnce();
    expect(previousTrack.stop).not.toHaveBeenCalled();
    expect(inputMediaStream.removeTrack).not.toHaveBeenCalled();
    expect(inputMediaStream.addTrack).not.toHaveBeenCalled();
  });
});
