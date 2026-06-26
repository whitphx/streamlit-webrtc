import { afterEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import InputMediaControls from "./InputMediaControls";

afterEach(() => {
  cleanup();
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
});
