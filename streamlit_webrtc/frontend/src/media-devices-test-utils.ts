import { vi } from "vitest";

export function makeDevice(
  deviceId: string,
  kind: MediaDeviceKind,
  label = `${deviceId} label`,
): MediaDeviceInfo {
  return {
    deviceId,
    groupId: `${deviceId}-group`,
    kind,
    label,
    toJSON: () => ({}),
  };
}

// `navigator.mediaDevices` does not exist in jsdom, so tests that reach it
// bring their own. The listener pair is stubbed for every caller because the
// device list is watched wherever it is read.
export function stubMediaDevices(mediaDevices: Partial<MediaDevices>) {
  vi.stubGlobal("navigator", {
    mediaDevices: {
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      ...mediaDevices,
    },
  });
}
