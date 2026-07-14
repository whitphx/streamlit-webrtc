import { afterEach, describe, expect, it, vi } from "vitest";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { useEffect } from "react";
import { WebRtcStreamerInner } from "./WebRtcStreamer";
import { useWebRtc } from "./webrtc";
import { persistDeviceIds } from "./device-storage";

vi.mock("streamlit-component-lib-react-hooks", () => ({
  useRenderData: vi.fn(),
}));

vi.mock("./webrtc", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./webrtc")>();
  return {
    ...actual,
    useWebRtc: vi.fn(),
  };
});

vi.mock("./device-storage", () => ({
  loadPersistedDeviceIds: () => ({
    video: "old-video",
    audio: "old-audio",
  }),
  persistDeviceIds: vi.fn(),
}));

vi.mock("./DeviceSelect/DeviceSelectForm", () => ({
  default: function MockDeviceSelectForm(props: {
    onSelectionResolved: (devices: { video?: string; audio?: string }) => void;
    onVideoSelect: (deviceId: string) => void;
    switchError?: Error | null;
  }) {
    const { onSelectionResolved, onVideoSelect, switchError } = props;
    useEffect(() => {
      onSelectionResolved({ video: "old-video", audio: "old-audio" });
    }, [onSelectionResolved]);
    return (
      <div>
        <button type="button" onClick={() => onVideoSelect("new-video")}>
          Choose another camera
        </button>
        {switchError != null && <div role="alert">{switchError.message}</div>}
      </div>
    );
  },
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function makeStream() {
  const videoTrack = { enabled: true };
  const audioTrack = { enabled: true };
  return {
    getVideoTracks: () => [videoTrack],
    getAudioTracks: () => [audioTrack],
  } as unknown as MediaStream;
}

function renderStreamer({
  mediaToggleControls = true,
  updateInputDevice = vi
    .fn<(kind: "video" | "audio", deviceId: string) => Promise<void>>()
    .mockResolvedValue(undefined),
}: {
  mediaToggleControls?: boolean;
  updateInputDevice?: (
    kind: "video" | "audio",
    deviceId: string,
  ) => Promise<void>;
} = {}) {
  vi.mocked(useWebRtc).mockReturnValue({
    state: {
      webRtcState: "PLAYING",
      sdpOffer: null,
      iceCandidates: {},
      outputMediaStream: null,
      inputMediaStream: makeStream(),
      error: null,
    },
    start: vi.fn(),
    stop: vi.fn(),
    updateInputDevice,
  });

  render(
    <WebRtcStreamerInner
      disabled={false}
      mode="SENDRECV"
      componentKey="test-key"
      desiredPlayingState={undefined}
      sdpAnswerJson={undefined}
      rtcConfiguration={undefined}
      mediaStreamConstraints={{ audio: true, video: true }}
      sendbackVideo={true}
      sendbackAudio={true}
      videoHtmlAttrs={{}}
      audioHtmlAttrs={{}}
      mediaToggleControls={mediaToggleControls}
      onComponentValueChange={vi.fn()}
    />,
  );

  return { updateInputDevice };
}

describe("<WebRtcStreamerInner />", () => {
  it("shows input media controls by default", () => {
    renderStreamer();

    expect(
      screen.getByRole("button", { name: "Turn camera off" }),
    ).not.toBeNull();
    expect(
      screen.getByRole("button", { name: "Mute microphone" }),
    ).not.toBeNull();
  });

  it("hides input media controls when disabled", () => {
    renderStreamer({ mediaToggleControls: false });

    expect(
      screen.queryByRole("button", { name: "Turn camera off" }),
    ).toBeNull();
    expect(
      screen.queryByRole("button", { name: "Mute microphone" }),
    ).toBeNull();
  });

  it("shows the device selector while streaming", () => {
    renderStreamer();

    expect(
      screen.getByRole("button", { name: "Select Device" }),
    ).not.toBeNull();
  });

  it("does not switch devices when the selector synchronizes on mount", async () => {
    const { updateInputDevice } = renderStreamer();

    fireEvent.click(screen.getByRole("button", { name: "Select Device" }));
    await screen.findByRole("button", { name: "Choose another camera" });

    expect(updateInputDevice).not.toHaveBeenCalled();
  });

  it("persists a user-selected device only after switching succeeds", async () => {
    let finishSwitch: (() => void) | undefined;
    const updateInputDevice = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          finishSwitch = resolve;
        }),
    );
    renderStreamer({ updateInputDevice });
    fireEvent.click(screen.getByRole("button", { name: "Select Device" }));
    fireEvent.click(
      await screen.findByRole("button", { name: "Choose another camera" }),
    );

    expect(updateInputDevice).toHaveBeenCalledWith("video", "new-video");
    expect(persistDeviceIds).not.toHaveBeenCalled();

    await act(async () => finishSwitch?.());
    expect(persistDeviceIds).toHaveBeenCalledWith("test-key", {
      video: "new-video",
      audio: "old-audio",
    });
  });

  it("shows a switching error and keeps the previous selection", async () => {
    const updateInputDevice = vi
      .fn()
      .mockRejectedValue(
        new DOMException("Device is busy", "NotReadableError"),
      );
    renderStreamer({ updateInputDevice });
    fireEvent.click(screen.getByRole("button", { name: "Select Device" }));
    fireEvent.click(
      await screen.findByRole("button", { name: "Choose another camera" }),
    );

    expect((await screen.findByRole("alert")).textContent).toContain(
      "Device is busy",
    );
    expect(persistDeviceIds).not.toHaveBeenCalled();
  });
});
