import { cleanup, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useWebRtc } from ".";

afterEach(() => {
  cleanup();
});

describe("useWebRtc", () => {
  it("rejects device switching without an active input stream", async () => {
    const { result } = renderHook(() =>
      useWebRtc(
        {
          mode: "SENDRECV",
          desiredPlayingState: undefined,
          sdpAnswerJson: undefined,
          rtcConfiguration: undefined,
          mediaStreamConstraints: { video: true, audio: true },
          sendbackVideo: true,
          sendbackAudio: true,
        },
        undefined,
        undefined,
        vi.fn(),
        vi.fn(),
      ),
    );

    await expect(
      result.current.updateInputDevice("video", "next-video"),
    ).rejects.toThrow(
      "Cannot switch input device without an active WebRTC input stream",
    );
  });
});
