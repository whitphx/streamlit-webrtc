import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { openInputMediaStream } from "./open-input-media-stream";

const STALE_VIDEO_ID = "stale-video";
const LIVE_VIDEO_ID = "live-video";
const LIVE_AUDIO_ID = "live-audio";

function makeStream(): MediaStream {
  return { getTracks: () => [] } as unknown as MediaStream;
}

function makeDevice(kind: MediaDeviceKind, deviceId: string): MediaDeviceInfo {
  return { kind, deviceId, groupId: "", label: deviceId } as MediaDeviceInfo;
}

function overconstrainedError(): Error {
  const error = new Error("Requested device not found");
  error.name = "OverconstrainedError";
  return error;
}

const getUserMedia = vi.fn<() => Promise<MediaStream>>();
const enumerateDevices = vi.fn<() => Promise<MediaDeviceInfo[]>>();

beforeEach(() => {
  vi.stubGlobal("navigator", {
    mediaDevices: { getUserMedia, enumerateDevices },
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.resetAllMocks();
});

describe("openInputMediaStream()", () => {
  it("returns null when the constraints ask for no media", async () => {
    expect(
      await openInputMediaStream(
        { video: false, audio: false },
        undefined,
        undefined,
      ),
    ).toBeNull();
    expect(getUserMedia).not.toHaveBeenCalled();
  });

  it("opens the requested devices without a retry when they resolve", async () => {
    const stream = makeStream();
    getUserMedia.mockResolvedValue(stream);

    const opened = await openInputMediaStream(
      { video: true, audio: false },
      LIVE_VIDEO_ID,
      undefined,
    );

    expect(opened).toEqual({ stream, unavailableDeviceKinds: [] });
    expect(getUserMedia).toHaveBeenCalledTimes(1);
    expect(getUserMedia).toHaveBeenCalledWith({
      video: { deviceId: { exact: LIVE_VIDEO_ID } },
      audio: false,
    });
    expect(enumerateDevices).not.toHaveBeenCalled();
  });

  it("retries without a device ID that no longer resolves", async () => {
    const stream = makeStream();
    getUserMedia
      .mockRejectedValueOnce(overconstrainedError())
      .mockResolvedValueOnce(stream);
    enumerateDevices.mockResolvedValue([
      makeDevice("videoinput", LIVE_VIDEO_ID),
    ]);

    const opened = await openInputMediaStream(
      { video: true, audio: false },
      STALE_VIDEO_ID,
      undefined,
    );

    expect(opened).toEqual({ stream, unavailableDeviceKinds: ["video"] });
    expect(getUserMedia).toHaveBeenLastCalledWith({
      video: true,
      audio: false,
    });
  });

  it("keeps a device ID that still resolves while dropping the dead one", async () => {
    getUserMedia
      .mockRejectedValueOnce(overconstrainedError())
      .mockResolvedValueOnce(makeStream());
    enumerateDevices.mockResolvedValue([
      makeDevice("videoinput", LIVE_VIDEO_ID),
      makeDevice("audioinput", LIVE_AUDIO_ID),
    ]);

    const opened = await openInputMediaStream(
      { video: true, audio: true },
      STALE_VIDEO_ID,
      LIVE_AUDIO_ID,
    );

    expect(opened?.unavailableDeviceKinds).toEqual(["video"]);
    expect(getUserMedia).toHaveBeenLastCalledWith({
      video: true,
      audio: { deviceId: { exact: LIVE_AUDIO_ID } },
    });
  });

  it("rethrows when every requested device exists, so another constraint is at fault", async () => {
    const error = overconstrainedError();
    getUserMedia.mockRejectedValue(error);
    enumerateDevices.mockResolvedValue([
      makeDevice("videoinput", LIVE_VIDEO_ID),
    ]);

    await expect(
      openInputMediaStream(
        { video: { frameRate: { exact: 1000 } } },
        LIVE_VIDEO_ID,
        undefined,
      ),
    ).rejects.toBe(error);
    expect(getUserMedia).toHaveBeenCalledTimes(1);
  });

  it("ignores a stored ID for a kind the app disabled", async () => {
    const error = overconstrainedError();
    getUserMedia.mockRejectedValue(error);
    enumerateDevices.mockResolvedValue([
      makeDevice("videoinput", LIVE_VIDEO_ID),
    ]);

    // `audio: false` means the stale audio ID never reached the constraints,
    // so it cannot be what the browser rejected.
    await expect(
      openInputMediaStream(
        { video: true, audio: false },
        LIVE_VIDEO_ID,
        "stale-audio",
      ),
    ).rejects.toBe(error);
    expect(getUserMedia).toHaveBeenCalledTimes(1);
  });

  it("leaves a device ID that the app itself constrained", async () => {
    const error = overconstrainedError();
    getUserMedia.mockRejectedValue(error);
    enumerateDevices.mockResolvedValue([]);

    await expect(
      openInputMediaStream(
        { video: { deviceId: { exact: "app-chosen-video" } } },
        undefined,
        undefined,
      ),
    ).rejects.toBe(error);
    expect(getUserMedia).toHaveBeenCalledTimes(1);
  });

  it("does not retry errors other than OverconstrainedError", async () => {
    const error = new DOMException("Permission denied", "NotAllowedError");
    getUserMedia.mockRejectedValue(error);

    await expect(
      openInputMediaStream({ video: true }, STALE_VIDEO_ID, undefined),
    ).rejects.toBe(error);
    expect(getUserMedia).toHaveBeenCalledTimes(1);
    expect(enumerateDevices).not.toHaveBeenCalled();
  });

  it("drops every requested ID when the device list is unreadable", async () => {
    getUserMedia
      .mockRejectedValueOnce(overconstrainedError())
      .mockResolvedValueOnce(makeStream());
    enumerateDevices.mockRejectedValue(new Error("enumeration failed"));

    const opened = await openInputMediaStream(
      { video: true, audio: true },
      STALE_VIDEO_ID,
      LIVE_AUDIO_ID,
    );

    expect(opened?.unavailableDeviceKinds).toEqual(["video", "audio"]);
    expect(getUserMedia).toHaveBeenLastCalledWith({
      video: true,
      audio: true,
    });
  });

  it("rethrows when no device ID was requested at all", async () => {
    const error = overconstrainedError();
    getUserMedia.mockRejectedValue(error);

    await expect(
      openInputMediaStream({ video: true }, undefined, undefined),
    ).rejects.toBe(error);
    expect(getUserMedia).toHaveBeenCalledTimes(1);
  });
});
