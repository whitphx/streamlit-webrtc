import { describe, expect, it, vi } from "vitest";
import { connectReducer, initialState } from "./reducer";

describe("connectReducer", () => {
  it("serializes frontend termination events with a stopped playing state", () => {
    const onComponentValueChange = vi.fn();
    const reducer = connectReducer(onComponentValueChange);
    const frontendEvent = {
      id: "event-1",
      type: "connection_lost" as const,
      reason: "pc.connectionState=failed",
      at: 123,
    };

    reducer(
      { ...initialState, webRtcState: "PLAYING" },
      { type: "STOPPING", frontendEvent },
    );

    expect(onComponentValueChange).toHaveBeenCalledWith({
      playing: false,
      sdpOffer: "",
      iceCandidates: {},
      frontendEvent,
    });
  });
});
