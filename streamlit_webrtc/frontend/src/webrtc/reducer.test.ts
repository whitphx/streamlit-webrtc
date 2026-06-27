import { describe, expect, it } from "vitest";
import { Action } from "./actions";
import { reducer, State } from "./reducer";

const errorActions = [
  "SET_OFFER_ERROR",
  "PROCESS_ANSWER_ERROR",
  "ERROR",
] as const;

function makeStateWithStreams(): State {
  return {
    webRtcState: "PLAYING",
    sdpOffer: {} as RTCSessionDescription,
    iceCandidates: {
      candidate: {} as RTCIceCandidate,
    },
    outputMediaStream: {} as MediaStream,
    inputMediaStream: {} as MediaStream,
    error: null,
  };
}

describe("reducer", () => {
  it.each(errorActions)("clears media streams on %s", (type) => {
    const error = new Error("test error");
    const action = { type, error } satisfies Action;

    const nextState = reducer(makeStateWithStreams(), action);

    expect(nextState.webRtcState).toBe("STOPPED");
    expect(nextState.sdpOffer).toBeNull();
    expect(nextState.iceCandidates).toEqual({});
    expect(nextState.outputMediaStream).toBeNull();
    expect(nextState.inputMediaStream).toBeNull();
    expect(nextState.error).toBe(error);
  });
});
