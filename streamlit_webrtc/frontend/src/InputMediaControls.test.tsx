import { afterEach, describe, expect, it, vi } from "vitest";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import InputMediaControls from "./InputMediaControls";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function makeStream({
  videoTrack,
  audioTrack,
}: {
  videoTrack?: Pick<MediaStreamTrack, "enabled">;
  audioTrack?: Pick<MediaStreamTrack, "enabled">;
}) {
  return {
    getVideoTracks: () => (videoTrack ? [videoTrack] : []),
    getAudioTracks: () => (audioTrack ? [audioTrack] : []),
  } as unknown as MediaStream;
}

function makeDevice(deviceId: string, kind: MediaDeviceKind): MediaDeviceInfo {
  return {
    deviceId,
    groupId: `${deviceId}-group`,
    kind,
    label: `${deviceId} label`,
    toJSON: () => ({}),
  };
}

function stubDevices(devices: MediaDeviceInfo[]) {
  vi.stubGlobal("navigator", {
    mediaDevices: {
      enumerateDevices: vi.fn().mockResolvedValue(devices),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    },
  });
}

const TWO_OF_EACH = [
  makeDevice("cam-1", "videoinput"),
  makeDevice("cam-2", "videoinput"),
  makeDevice("mic-1", "audioinput"),
  makeDevice("mic-2", "audioinput"),
];

describe("<InputMediaControls />", () => {
  it("toggles camera and microphone tracks", () => {
    const videoTrack = { enabled: true };
    const audioTrack = { enabled: true };
    const stream = makeStream({ videoTrack, audioTrack });

    render(<InputMediaControls stream={stream} />);

    const cameraButton = screen.getByRole("button", {
      name: "Turn camera off",
    });
    const microphoneButton = screen.getByRole("button", {
      name: "Mute microphone",
    });

    expect(cameraButton.getAttribute("aria-pressed")).toBe("false");
    expect(microphoneButton.getAttribute("aria-pressed")).toBe("false");

    fireEvent.click(cameraButton);
    fireEvent.click(microphoneButton);

    expect(videoTrack.enabled).toBe(false);
    expect(audioTrack.enabled).toBe(false);
    expect(
      screen
        .getByRole("button", { name: "Turn camera on" })
        .getAttribute("aria-pressed"),
    ).toBe("true");
    expect(
      screen
        .getByRole("button", { name: "Unmute microphone" })
        .getAttribute("aria-pressed"),
    ).toBe("true");
  });

  it("renders only controls for existing tracks", () => {
    const stream = makeStream({ audioTrack: { enabled: true } });

    render(<InputMediaControls stream={stream} />);

    expect(screen.queryByRole("button", { name: /camera/i })).toBeNull();
    expect(
      screen.getByRole("button", { name: "Mute microphone" }),
    ).not.toBeNull();
  });

  it("switches the input device from the control row", async () => {
    stubDevices(TWO_OF_EACH);
    const onSelectDevice = vi.fn().mockResolvedValue(undefined);

    render(
      <InputMediaControls
        stream={makeStream({
          videoTrack: { enabled: true },
          audioTrack: { enabled: true },
        })}
        selectedDeviceIds={{ video: "cam-1", audio: "mic-1" }}
        onSelectDevice={onSelectDevice}
      />,
    );

    const cameraSelect = await screen.findByRole("combobox", {
      name: "Select camera",
    });
    fireEvent.change(cameraSelect, { target: { value: "cam-2" } });
    expect(onSelectDevice).toHaveBeenCalledWith("video", "cam-2");

    fireEvent.change(
      screen.getByRole("combobox", { name: "Select microphone" }),
      { target: { value: "mic-2" } },
    );
    expect(onSelectDevice).toHaveBeenCalledWith("audio", "mic-2");
  });

  it("offers no picker for a kind with nothing to switch to", async () => {
    stubDevices([
      makeDevice("cam-1", "videoinput"),
      makeDevice("mic-1", "audioinput"),
      makeDevice("mic-2", "audioinput"),
    ]);

    render(
      <InputMediaControls
        stream={makeStream({
          videoTrack: { enabled: true },
          audioTrack: { enabled: true },
        })}
        selectedDeviceIds={{ video: "cam-1", audio: "mic-1" }}
        onSelectDevice={vi.fn().mockResolvedValue(undefined)}
      />,
    );

    await screen.findByRole("combobox", { name: "Select microphone" });
    expect(
      screen.queryByRole("combobox", { name: "Select camera" }),
    ).toBeNull();
  });

  it("holds the pending device until the switch settles, then reverts if it fails", async () => {
    stubDevices(TWO_OF_EACH);
    let rejectSwitch: ((error: Error) => void) | undefined;
    const onSelectDevice = vi.fn(
      () =>
        new Promise<void>((_resolve, reject) => {
          rejectSwitch = reject;
        }),
    );

    render(
      <InputMediaControls
        stream={makeStream({ videoTrack: { enabled: true } })}
        selectedDeviceIds={{ video: "cam-1" }}
        onSelectDevice={onSelectDevice}
      />,
    );

    const cameraSelect = (await screen.findByRole("combobox", {
      name: "Select camera",
    })) as HTMLSelectElement;
    fireEvent.change(cameraSelect, { target: { value: "cam-2" } });
    // The parent confirms the new device only once the switch succeeds, so the
    // picker holds the pending one meanwhile instead of snapping back.
    expect(cameraSelect.value).toBe("cam-2");

    await act(async () => rejectSwitch?.(new Error("Device is busy")));

    expect(cameraSelect.value).toBe("cam-1");
  });

  it("offers no picker when the stream cannot switch devices", async () => {
    stubDevices(TWO_OF_EACH);

    render(
      <InputMediaControls
        stream={makeStream({
          videoTrack: { enabled: true },
          audioTrack: { enabled: true },
        })}
        selectedDeviceIds={{ video: "cam-1", audio: "mic-1" }}
      />,
    );

    await screen.findByRole("button", { name: "Turn camera off" });
    expect(screen.queryAllByRole("combobox")).toHaveLength(0);
  });
});
