import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useMediaInputDevices } from "./use-media-input-devices";
import { makeDevice, stubMediaDevices } from "./media-devices-test-utils";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useMediaInputDevices()", () => {
  it("splits the enumerated devices by kind", async () => {
    stubMediaDevices({
      enumerateDevices: vi
        .fn()
        .mockResolvedValue([
          makeDevice("camera", "videoinput"),
          makeDevice("microphone", "audioinput"),
          makeDevice("speaker", "audiooutput"),
        ]),
    });

    const { result } = renderHook(() => useMediaInputDevices());

    await waitFor(() =>
      expect(result.current.devices.video.map((d) => d.deviceId)).toEqual([
        "camera",
      ]),
    );
    expect(result.current.devices.audio.map((d) => d.deviceId)).toEqual([
      "microphone",
    ]);
    expect(result.current.unavailable).toBe(false);
  });

  // Reporting these as devices would let a caller resolve a selection to the
  // empty ID and store it over the one the user actually chose.
  it("ignores the placeholder entries reported before permission is granted", async () => {
    stubMediaDevices({
      enumerateDevices: vi
        .fn()
        .mockResolvedValue([
          makeDevice("", "videoinput", ""),
          makeDevice("", "audioinput", ""),
        ]),
    });

    const { result } = renderHook(() => useMediaInputDevices());

    await act(async () => undefined);
    expect(result.current.devices).toEqual({ video: [], audio: [] });
  });

  it("re-enumerates when the device list changes", async () => {
    const listeners: Array<() => void> = [];
    const enumerateDevices = vi
      .fn()
      .mockResolvedValueOnce([makeDevice("camera", "videoinput")])
      .mockResolvedValueOnce([
        makeDevice("camera", "videoinput"),
        makeDevice("usb-camera", "videoinput"),
      ]);
    stubMediaDevices({
      enumerateDevices,
      addEventListener: vi.fn((_type: string, listener: EventListener) =>
        listeners.push(listener as () => void),
      ),
    });

    const { result } = renderHook(() => useMediaInputDevices());
    await waitFor(() => expect(result.current.devices.video).toHaveLength(1));

    await act(async () => listeners.forEach((listener) => listener()));

    expect(result.current.devices.video.map((d) => d.deviceId)).toEqual([
      "camera",
      "usb-camera",
    ]);
  });

  it("keeps the latest result when an earlier enumeration resolves late", async () => {
    let resolveOnMount: ((devices: MediaDeviceInfo[]) => void) | undefined;
    let resolveRefresh: ((devices: MediaDeviceInfo[]) => void) | undefined;
    stubMediaDevices({
      enumerateDevices: vi
        .fn()
        .mockImplementationOnce(
          () => new Promise((resolve) => (resolveOnMount = resolve)),
        )
        .mockImplementationOnce(
          () => new Promise((resolve) => (resolveRefresh = resolve)),
        ),
    });

    const { result } = renderHook(() => useMediaInputDevices());
    // The enumeration on mount runs before the permission prompt is answered,
    // so its labels are empty. The refresh a consumer makes once permission is
    // granted is the authoritative one, whichever settles first.
    await act(async () => {
      void result.current.refresh();
    });

    await act(async () =>
      resolveRefresh?.([makeDevice("labeled", "videoinput")]),
    );
    await act(async () =>
      resolveOnMount?.([makeDevice("stale", "videoinput")]),
    );

    expect(result.current.devices.video.map((d) => d.deviceId)).toEqual([
      "labeled",
    ]);
  });

  it("does not settle an awaited refresh on a result it discarded", async () => {
    const pending: Array<(devices: MediaDeviceInfo[]) => void> = [];
    stubMediaDevices({
      enumerateDevices: vi.fn(
        () =>
          new Promise<MediaDeviceInfo[]>((resolve) => pending.push(resolve)),
      ),
    });

    const { result } = renderHook(() => useMediaInputDevices());

    let awaitedRefreshSettled = false;
    await act(async () => {
      void result.current.refresh().then(() => {
        awaitedRefreshSettled = true;
      });
    });
    // A `devicechange` between the refresh and its result supersedes it.
    await act(async () => {
      void result.current.refresh();
    });

    await act(async () =>
      pending[1]?.([makeDevice("discarded", "videoinput")]),
    );
    expect(awaitedRefreshSettled).toBe(false);

    await act(async () => pending[2]?.([makeDevice("newest", "videoinput")]));
    expect(awaitedRefreshSettled).toBe(true);
    expect(result.current.devices.video.map((d) => d.deviceId)).toEqual([
      "newest",
    ]);
  });

  // `navigator.mediaDevices` is undefined outside a secure context, so every
  // access has to tolerate it being missing rather than throwing on mount.
  it("reports the media API as unavailable when devices cannot be enumerated", () => {
    vi.stubGlobal("navigator", {});

    const { result } = renderHook(() => useMediaInputDevices());

    expect(result.current.unavailable).toBe(true);
    expect(result.current.devices.video).toEqual([]);
    expect(result.current.devices.audio).toEqual([]);
  });
});
