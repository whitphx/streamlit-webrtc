import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import DeviceSelect from "./DeviceSelect";

vi.mock("streamlit-component-lib", () => ({
  Streamlit: { setFrameHeight: vi.fn() },
}));

vi.mock("./VideoPreview", () => ({
  default: () => <div />,
}));

function makeDevice(deviceId: string): MediaDeviceInfo {
  return {
    deviceId,
    groupId: "video-group",
    kind: "videoinput",
    label: deviceId,
    toJSON: () => ({}),
  };
}

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
    vi.stubGlobal("navigator", {
      mediaDevices: {
        getUserMedia: vi.fn().mockResolvedValue({
          getTracks: () => [],
          getVideoTracks: () => [],
          getAudioTracks: () => [],
        }),
        enumerateDevices: vi
          .fn()
          .mockResolvedValue([
            makeDevice("old-video"),
            makeDevice("first-video"),
            makeDevice("second-video"),
          ]),
        ondevicechange: null,
      },
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
});
