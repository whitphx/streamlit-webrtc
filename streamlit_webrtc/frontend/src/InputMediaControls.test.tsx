import { afterEach, describe, expect, it, vi } from "vitest";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import InputMediaControls from "./InputMediaControls";
import { makeDevice, stubMediaDevices } from "./media-devices-test-utils";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

interface FakeTrack {
  enabled: boolean;
}

function makeTrack({
  deviceId,
  readyState = "live",
}: {
  deviceId?: string;
  readyState?: MediaStreamTrackState;
} = {}): FakeTrack {
  return {
    enabled: true,
    readyState,
    getSettings: () => ({ deviceId }),
  } as unknown as FakeTrack;
}

function makeStream({
  videoTrack,
  audioTrack,
}: {
  videoTrack?: FakeTrack;
  audioTrack?: FakeTrack;
}) {
  return {
    getVideoTracks: () => (videoTrack ? [videoTrack] : []),
    getAudioTracks: () => (audioTrack ? [audioTrack] : []),
  } as unknown as MediaStream;
}

function stubDevices(devices: MediaDeviceInfo[]) {
  stubMediaDevices({ enumerateDevices: vi.fn().mockResolvedValue(devices) });
}

const TWO_OF_EACH = [
  makeDevice("cam-1", "videoinput"),
  makeDevice("cam-2", "videoinput"),
  makeDevice("mic-1", "audioinput"),
  makeDevice("mic-2", "audioinput"),
];

describe("<InputMediaControls />", () => {
  it("toggles camera and microphone tracks", () => {
    const videoTrack = makeTrack({ deviceId: "cam-1" });
    const audioTrack = makeTrack({ deviceId: "mic-1" });
    const stream = makeStream({ videoTrack, audioTrack });

    render(
      <InputMediaControls
        stream={stream}
        onSelectDevice={vi.fn().mockResolvedValue(undefined)}
      />,
    );

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
    const stream = makeStream({ audioTrack: makeTrack({ deviceId: "mic-1" }) });

    render(
      <InputMediaControls
        stream={stream}
        onSelectDevice={vi.fn().mockResolvedValue(undefined)}
      />,
    );

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
          videoTrack: makeTrack({ deviceId: "cam-1" }),
          audioTrack: makeTrack({ deviceId: "mic-1" }),
        })}
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
          videoTrack: makeTrack({ deviceId: "cam-1" }),
          audioTrack: makeTrack({ deviceId: "mic-1" }),
        })}
        onSelectDevice={vi.fn().mockResolvedValue(undefined)}
      />,
    );

    await screen.findByRole("combobox", { name: "Select microphone" });
    expect(
      screen.queryByRole("combobox", { name: "Select camera" }),
    ).toBeNull();
  });

  it("still offers a picker once the live device is unplugged", async () => {
    // Only the survivor is enumerated, and the track of the camera that went
    // away has ended.
    stubDevices([makeDevice("cam-2", "videoinput")]);
    const onSelectDevice = vi.fn().mockResolvedValue(undefined);

    render(
      <InputMediaControls
        stream={makeStream({
          videoTrack: makeTrack({ deviceId: "cam-1", readyState: "ended" }),
        })}
        onSelectDevice={onSelectDevice}
      />,
    );

    const cameraSelect = (await screen.findByRole("combobox", {
      name: "Select camera",
    })) as HTMLSelectElement;
    expect(cameraSelect.value).toBe("");

    fireEvent.change(cameraSelect, { target: { value: "cam-2" } });
    expect(onSelectDevice).toHaveBeenCalledWith("video", "cam-2");
  });

  it("can pick the same camera again once it is plugged back in", async () => {
    // The camera is back under the ID it had before, but the track that ended
    // when it was unplugged stays ended, so nothing is feeding the connection
    // and that ID has to remain selectable.
    stubDevices([makeDevice("cam-1", "videoinput")]);
    const onSelectDevice = vi.fn().mockResolvedValue(undefined);

    render(
      <InputMediaControls
        stream={makeStream({
          videoTrack: makeTrack({ deviceId: "cam-1", readyState: "ended" }),
        })}
        onSelectDevice={onSelectDevice}
      />,
    );

    const cameraSelect = (await screen.findByRole("combobox", {
      name: "Select camera",
    })) as HTMLSelectElement;
    expect(cameraSelect.value).toBe("");

    fireEvent.change(cameraSelect, { target: { value: "cam-1" } });
    expect(onSelectDevice).toHaveBeenCalledWith("video", "cam-1");
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
        stream={makeStream({ videoTrack: makeTrack({ deviceId: "cam-1" }) })}
        onSelectDevice={onSelectDevice}
      />,
    );

    const cameraSelect = (await screen.findByRole("combobox", {
      name: "Select camera",
    })) as HTMLSelectElement;
    fireEvent.change(cameraSelect, { target: { value: "cam-2" } });
    // The switch has not reached a track yet, so the picker holds the pending
    // device rather than snapping back to the one still live.
    expect(cameraSelect.value).toBe("cam-2");

    await act(async () => rejectSwitch?.(new Error("Device is busy")));

    expect(cameraSelect.value).toBe("cam-1");
  });

  it("drops a pending device when the stream it was asked for is replaced", async () => {
    stubDevices(TWO_OF_EACH);
    let finishSwitch: (() => void) | undefined;
    const onSelectDevice = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          finishSwitch = resolve;
        }),
    );
    const streamer = (stream: MediaStream) => (
      <InputMediaControls stream={stream} onSelectDevice={onSelectDevice} />
    );

    const { rerender } = render(
      streamer(makeStream({ videoTrack: makeTrack({ deviceId: "cam-1" }) })),
    );

    const cameraSelect = (await screen.findByRole("combobox", {
      name: "Select camera",
    })) as HTMLSelectElement;
    fireEvent.change(cameraSelect, { target: { value: "cam-2" } });
    expect(cameraSelect.value).toBe("cam-2");
    // The displayed device is set before the switch is asked for, so without
    // this the switch could never be made and the rest would still hold.
    expect(onSelectDevice).toHaveBeenCalledWith("video", "cam-2");

    // The switch was asked for on a stream that is no longer here, so the
    // device it is waiting on describes nothing about the one that replaced it.
    await act(async () =>
      rerender(
        streamer(makeStream({ videoTrack: makeTrack({ deviceId: "cam-1" }) })),
      ),
    );
    expect(cameraSelect.value).toBe("cam-1");

    await act(async () => finishSwitch?.());
    expect(cameraSelect.value).toBe("cam-1");
  });

  it("holds the picker inert while its kind is turned off", async () => {
    stubDevices(TWO_OF_EACH);

    render(
      <InputMediaControls
        stream={makeStream({ videoTrack: makeTrack({ deviceId: "cam-1" }) })}
        onSelectDevice={vi.fn().mockResolvedValue(undefined)}
      />,
    );

    const cameraSelect = (await screen.findByRole("combobox", {
      name: "Select camera",
    })) as HTMLSelectElement;
    expect(cameraSelect.disabled).toBe(false);

    // Switching opens the chosen device, so offering it under a camera the
    // user has turned off would light the indicator of a camera shown as off.
    fireEvent.click(screen.getByRole("button", { name: "Turn camera off" }));
    expect(cameraSelect.disabled).toBe(true);
  });
});
