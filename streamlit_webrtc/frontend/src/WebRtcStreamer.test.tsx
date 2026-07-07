import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { WebRtcStreamerInner } from "./WebRtcStreamer";
import { useWebRtc } from "./webrtc";

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
}: {
  mediaToggleControls?: boolean;
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
  });

  render(
    <WebRtcStreamerInner
      disabled={false}
      mode="SENDRECV"
      componentKey="test-key"
      desiredPlayingState={undefined}
      sdpAnswerJson={undefined}
      answererIceCandidatesJson={undefined}
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
});
