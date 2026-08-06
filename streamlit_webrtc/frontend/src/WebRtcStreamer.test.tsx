import { afterEach, describe, expect, it, vi } from "vitest";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { useEffect } from "react";
import { WebRtcStreamerInner } from "./WebRtcStreamer";
import { useWebRtc } from "./webrtc";
import { persistDeviceIds } from "./device-storage";
import { makeDevice, stubMediaDevices } from "./media-devices-test-utils";

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

let resolvedSelection: { video?: string; audio?: string } = {
  video: "old-video",
  audio: "old-audio",
};

vi.mock("./DeviceSelect/DeviceSelectForm", () => ({
  default: function MockDeviceSelectForm(props: {
    onSelectionResolved: (devices: { video?: string; audio?: string }) => void;
    onVideoSelect: (deviceId: string) => Promise<void> | void;
    onAudioSelect: (deviceId: string) => Promise<void> | void;
    switchError?: Error | null;
  }) {
    const { onSelectionResolved, onVideoSelect, onAudioSelect, switchError } =
      props;
    useEffect(() => {
      onSelectionResolved(resolvedSelection);
    }, [onSelectionResolved]);
    const selectVideo = () => {
      void Promise.resolve(onVideoSelect("new-video")).catch(() => undefined);
    };
    const selectAudio = () => {
      void Promise.resolve(onAudioSelect("new-audio")).catch(() => undefined);
    };
    return (
      <div>
        <button type="button" onClick={selectVideo}>
          Choose another camera
        </button>
        <button type="button" onClick={selectAudio}>
          Choose another microphone
        </button>
        {switchError != null && <div role="alert">{switchError.message}</div>}
      </div>
    );
  },
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
  resolvedSelection = { video: "old-video", audio: "old-audio" };
});

function stubDevices() {
  stubMediaDevices({
    enumerateDevices: vi
      .fn()
      .mockResolvedValue([
        makeDevice("old-video", "videoinput"),
        makeDevice("other-video", "videoinput"),
        makeDevice("old-audio", "audioinput"),
        makeDevice("other-audio", "audioinput"),
      ]),
  });
}

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
  webRtcState = "PLAYING",
  updateInputDevice = vi
    .fn<(kind: "video" | "audio", deviceId: string) => Promise<void>>()
    .mockResolvedValue(undefined),
}: {
  mediaToggleControls?: boolean;
  webRtcState?: "STOPPED" | "PLAYING";
  updateInputDevice?: (
    kind: "video" | "audio",
    deviceId: string,
  ) => Promise<void>;
} = {}) {
  const mockWebRtc = (inputMediaStream: MediaStream) =>
    vi.mocked(useWebRtc).mockReturnValue({
      state: {
        webRtcState,
        sdpOffer: null,
        iceCandidates: {},
        outputMediaStream: null,
        inputMediaStream,
        error: null,
      },
      start: vi.fn(),
      stop: vi.fn(),
      updateInputDevice,
    });
  mockWebRtc(makeStream());

  const streamer = () => (
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
    />
  );
  const { rerender } = render(streamer());

  const [, , , , onDevicesOpened, onDevicesUnavailable] =
    vi.mocked(useWebRtc).mock.calls[0];

  return {
    updateInputDevice,
    onDevicesOpened,
    onDevicesUnavailable,
    openAnotherStream: async () => {
      mockWebRtc(makeStream());
      await act(async () => rerender(streamer()));
    },
  };
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
    expect(persistDeviceIds).toHaveBeenCalledWith(
      "test-key",
      { video: "new-video", audio: "old-audio" },
      { clearing: false },
    );
  });

  it("keeps the stored selection when a fallback device opens", async () => {
    const { onDevicesOpened } = renderStreamer();

    act(() => onDevicesOpened({ video: "fallback-video" }));

    expect(persistDeviceIds).not.toHaveBeenCalled();
  });

  it("replaces a stored ID whose device no longer exists", async () => {
    const { onDevicesOpened, onDevicesUnavailable } = renderStreamer();

    act(() => onDevicesUnavailable(["video"]));
    act(() => onDevicesOpened({ video: "fallback-video" }));

    expect(persistDeviceIds).toHaveBeenLastCalledWith(
      "test-key",
      { video: "fallback-video", audio: "old-audio" },
      { clearing: false },
    );
  });

  it("drops a dead ID even when no replacement device opens", async () => {
    const { onDevicesUnavailable } = renderStreamer();

    // The capture that discovered this may still go on to fail; the ID has to
    // go regardless, or every later start repeats the rejected request.
    act(() => onDevicesUnavailable(["video"]));

    expect(persistDeviceIds).toHaveBeenCalledWith(
      "test-key",
      { audio: "old-audio" },
      { clearing: true },
    );
  });

  it("does not clear the stored selection when the picker resolves nothing", async () => {
    // The picker resolves empty while its device list is still empty, which
    // must not reach storage as a removal — the counterpart to the clearing
    // case below.
    resolvedSelection = {};
    renderStreamer({ webRtcState: "STOPPED" });

    fireEvent.click(screen.getByRole("button", { name: "Select Device" }));
    await screen.findByRole("button", { name: "Choose another camera" });

    expect(persistDeviceIds).toHaveBeenCalledWith(
      "test-key",
      { video: undefined, audio: undefined },
      { clearing: false },
    );
  });

  it("removes the stored entry when every kind is gone", async () => {
    const { onDevicesUnavailable } = renderStreamer();

    act(() => onDevicesUnavailable(["video", "audio"]));

    // `clearing` is what carries this past the write guard, which would
    // otherwise read the empty selection as the not-opened-yet state and leave
    // the dead IDs in storage for the next mount to retry.
    expect(persistDeviceIds).toHaveBeenCalledWith(
      "test-key",
      { video: undefined, audio: undefined },
      { clearing: true },
    );
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

  it("switches the input device from the control row while streaming", async () => {
    stubDevices();
    const { updateInputDevice } = renderStreamer();

    fireEvent.change(
      await screen.findByRole("combobox", { name: "Select camera" }),
      { target: { value: "other-video" } },
    );

    expect(updateInputDevice).toHaveBeenCalledWith("video", "other-video");
    await waitFor(() =>
      expect(persistDeviceIds).toHaveBeenCalledWith(
        "test-key",
        { video: "other-video", audio: "old-audio" },
        { clearing: false },
      ),
    );
  });

  it("shows a failure of a switch made from the control row", async () => {
    stubDevices();
    const updateInputDevice = vi
      .fn()
      .mockRejectedValue(
        new DOMException("Device is busy", "NotReadableError"),
      );
    renderStreamer({ updateInputDevice });

    fireEvent.change(
      await screen.findByRole("combobox", { name: "Select camera" }),
      { target: { value: "other-video" } },
    );

    // The form that reports a switch error is never opened from the control
    // row, so the failure has to surface in the main view instead.
    expect((await screen.findByRole("alert")).textContent).toContain(
      "Device is busy",
    );
    expect(persistDeviceIds).not.toHaveBeenCalled();
  });

  it("drops a switch error once another stream opens", async () => {
    stubDevices();
    const updateInputDevice = vi
      .fn()
      .mockRejectedValue(
        new DOMException("Device is busy", "NotReadableError"),
      );
    const { openAnotherStream } = renderStreamer({ updateInputDevice });
    fireEvent.change(
      await screen.findByRole("combobox", { name: "Select camera" }),
      { target: { value: "other-video" } },
    );
    await screen.findByRole("alert");

    // The error described the stream it happened on; a restart replaces that
    // one, and the alert sits above whatever is playing now.
    await openAnotherStream();

    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("preserves both confirmed IDs when video and audio switches overlap", async () => {
    let finishVideoSwitch: (() => void) | undefined;
    let finishAudioSwitch: (() => void) | undefined;
    const updateInputDevice = vi.fn((kind: "video" | "audio") => {
      return new Promise<void>((resolve) => {
        if (kind === "video") {
          finishVideoSwitch = resolve;
        } else {
          finishAudioSwitch = resolve;
        }
      });
    });
    renderStreamer({ updateInputDevice });
    fireEvent.click(screen.getByRole("button", { name: "Select Device" }));
    fireEvent.click(
      await screen.findByRole("button", { name: "Choose another camera" }),
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Choose another microphone" }),
    );

    await act(async () => finishAudioSwitch?.());
    await waitFor(() =>
      expect(persistDeviceIds).toHaveBeenLastCalledWith(
        "test-key",
        { video: "old-video", audio: "new-audio" },
        { clearing: false },
      ),
    );

    await act(async () => finishVideoSwitch?.());
    await waitFor(() =>
      expect(persistDeviceIds).toHaveBeenLastCalledWith(
        "test-key",
        { video: "new-video", audio: "new-audio" },
        { clearing: false },
      ),
    );
  });
});
