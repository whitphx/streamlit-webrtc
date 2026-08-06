import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import DeviceSelect from "./DeviceSelect";
import {
  makeDevice as makeMediaDevice,
  stubMediaDevices,
} from "../media-devices-test-utils";

vi.mock("streamlit-component-lib", () => ({
  Streamlit: { setFrameHeight: vi.fn() },
}));

vi.mock("./VideoPreview", () => ({
  default: () => <div />,
}));

function makeDevice(deviceId: string): MediaDeviceInfo {
  return makeMediaDevice(deviceId, "videoinput", deviceId);
}

const RESOLVED_STREAM = {
  getTracks: () => [],
  getVideoTracks: () => [],
  getAudioTracks: () => [],
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("<DeviceSelect />", () => {
  it("rolls back only the latest rejected selection", async () => {
    let rejectFirstSelection: ((error: Error) => void) | undefined;
    let rejectSecondSelection: ((error: Error) => void) | undefined;
    const onVideoSelect = vi
      .fn()
      .mockImplementationOnce(
        () =>
          new Promise<void>((_resolve, reject) => {
            rejectFirstSelection = reject;
          }),
      )
      .mockImplementationOnce(
        () =>
          new Promise<void>((_resolve, reject) => {
            rejectSecondSelection = reject;
          }),
      );
    stubMediaDevices({
      getUserMedia: vi.fn().mockResolvedValue(RESOLVED_STREAM),
      enumerateDevices: vi
        .fn()
        .mockResolvedValue([
          makeDevice("old-video"),
          makeDevice("first-video"),
          makeDevice("second-video"),
        ]),
    });

    render(
      <DeviceSelect
        video
        audio={false}
        defaultVideoDeviceId="old-video"
        defaultAudioDeviceId={undefined}
        onSelectionResolved={vi.fn()}
        onVideoSelect={onVideoSelect}
        onAudioSelect={vi.fn()}
      />,
    );

    const select = (await screen.findByLabelText(
      "Video Input",
    )) as HTMLSelectElement;
    fireEvent.change(select, { target: { value: "first-video" } });
    fireEvent.change(select, { target: { value: "second-video" } });
    expect(select.value).toBe("second-video");

    await act(async () =>
      rejectFirstSelection?.(new Error("First switch failed")),
    );
    expect(select.value).toBe("second-video");

    await act(async () =>
      rejectSecondSelection?.(new Error("Second switch failed")),
    );
    expect(select.value).toBe("old-video");
  });

  // The enumeration on mount runs before the permission prompt is answered.
  // Resolving a selection from what it reports would hand the caller an ID that
  // names no device, and the caller persists what it is given.
  it("resolves nothing while the device list is still unlabelled", async () => {
    const onSelectionResolved = vi.fn();
    stubMediaDevices({
      getUserMedia: vi.fn().mockReturnValue(new Promise(() => undefined)),
      enumerateDevices: vi
        .fn()
        .mockResolvedValue([makeMediaDevice("", "videoinput", "")]),
    });

    render(
      <DeviceSelect
        video
        audio={false}
        defaultVideoDeviceId="old-video"
        defaultAudioDeviceId={undefined}
        onSelectionResolved={onSelectionResolved}
        onVideoSelect={vi.fn()}
        onAudioSelect={vi.fn()}
      />,
    );

    await act(async () => undefined);
    expect(onSelectionResolved).not.toHaveBeenCalledWith(
      expect.objectContaining({ video: "" }),
    );
  });

  it("returns to the requested device when it comes back", async () => {
    let attached = [makeDevice("old-video"), makeDevice("spare")];
    const listeners: Array<() => void> = [];
    stubMediaDevices({
      getUserMedia: vi.fn().mockResolvedValue(RESOLVED_STREAM),
      enumerateDevices: vi.fn(() => Promise.resolve(attached)),
      addEventListener: vi.fn((_type: string, listener: EventListener) =>
        listeners.push(listener as () => void),
      ),
    });
    const emitDeviceChange = async (devices: MediaDeviceInfo[]) => {
      attached = devices;
      await act(async () => listeners.forEach((listener) => listener()));
    };

    render(
      <DeviceSelect
        video
        audio={false}
        defaultVideoDeviceId="old-video"
        defaultAudioDeviceId={undefined}
        onSelectionResolved={vi.fn()}
        onVideoSelect={vi.fn()}
        onAudioSelect={vi.fn()}
      />,
    );

    const select = (await screen.findByLabelText(
      "Video Input",
    )) as HTMLSelectElement;
    expect(select.value).toBe("old-video");

    // Unplugged: the only device left is the one the picker falls back to.
    await emitDeviceChange([makeDevice("spare")]);
    expect(select.value).toBe("spare");

    // Plugged back in: the request was never withdrawn, so it applies again.
    await emitDeviceChange([makeDevice("old-video"), makeDevice("spare")]);
    expect(select.value).toBe("old-video");
  });
});
