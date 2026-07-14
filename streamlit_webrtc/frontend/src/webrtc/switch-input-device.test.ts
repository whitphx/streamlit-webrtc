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

  it("stops acquired tracks when the requested kind is missing", async () => {
    const acquiredTrack = makeTrack("audio");
    vi.stubGlobal("navigator", {
      mediaDevices: {
        getUserMedia: vi.fn().mockResolvedValue(makeStream([acquiredTrack])),
      },
    });

    await expect(
      switchInputDevice(
        { getSenders: () => [] },
        makeStream([]),
        { video: true, audio: true },
        "video",
        "next-video",
      ),
    ).rejects.toThrow("No video track acquired");

    expect(acquiredTrack.stop).toHaveBeenCalledOnce();
  });

  it("stops the acquired track when no sender is available", async () => {
    const nextTrack = makeTrack("video");
    vi.stubGlobal("navigator", {
      mediaDevices: {
        getUserMedia: vi.fn().mockResolvedValue(makeStream([nextTrack])),
      },
    });

    await expect(
      switchInputDevice(
        { getSenders: () => [] },
        makeStream([]),
        { video: true, audio: true },
        "video",
        "next-video",
      ),
    ).rejects.toThrow("No sender found for video track");

    expect(nextTrack.stop).toHaveBeenCalledOnce();
  });

  it("serializes overlapping switches of the same kind", async () => {
    const previousTrack = makeTrack("video");
    const firstTrack = makeTrack("video");
    const secondTrack = makeTrack("video");
    const inputMediaStream = makeStream([previousTrack]);
    let finishFirstReplacement: (() => void) | undefined;
    const sender = {
      track: previousTrack,
      replaceTrack: vi.fn((nextTrack: MediaStreamTrack) => {
        if (nextTrack === firstTrack) {
          return new Promise<void>((resolve) => {
            finishFirstReplacement = () => {
              sender.track = firstTrack;
              resolve();
            };
          });
        }
        sender.track = nextTrack;
        return Promise.resolve();
      }),
    };
    const getUserMedia = vi
      .fn()
      .mockResolvedValueOnce(makeStream([firstTrack]))
      .mockResolvedValueOnce(makeStream([secondTrack]));
    vi.stubGlobal("navigator", { mediaDevices: { getUserMedia } });
    const peerConnection = {
      getSenders: () => [sender as unknown as RTCRtpSender],
    };

    const firstSwitch = switchInputDevice(
      peerConnection,
      inputMediaStream,
      { video: true, audio: true },
      "video",
      "first-video",
    );
    const secondSwitch = switchInputDevice(
      peerConnection,
      inputMediaStream,
      { video: true, audio: true },
      "video",
      "second-video",
    );

    await vi.waitFor(() => expect(sender.replaceTrack).toHaveBeenCalledOnce());
    expect(getUserMedia).toHaveBeenCalledOnce();

    finishFirstReplacement?.();
    await firstSwitch;
    await secondSwitch;

    expect(getUserMedia).toHaveBeenCalledTimes(2);
    expect(sender.replaceTrack).toHaveBeenNthCalledWith(1, firstTrack);
    expect(sender.replaceTrack).toHaveBeenNthCalledWith(2, secondTrack);
    expect(inputMediaStream.removeTrack).toHaveBeenNthCalledWith(
      1,
      previousTrack,
    );
    expect(inputMediaStream.removeTrack).toHaveBeenNthCalledWith(2, firstTrack);
    expect(previousTrack.stop).toHaveBeenCalledOnce();
    expect(firstTrack.stop).toHaveBeenCalledOnce();
    expect(secondTrack.stop).not.toHaveBeenCalled();
  });
});
