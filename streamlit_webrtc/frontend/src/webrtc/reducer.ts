import { ComponentValue } from "../component-value";
import { Action } from "./actions";

export type WebRtcState = "STOPPED" | "SIGNALLING" | "PLAYING" | "STOPPING";
export interface State {
  webRtcState: WebRtcState;
  sdpOffer: RTCSessionDescription | null;
  iceCandidates: Record<string, RTCIceCandidate>;  // key: candidate id for the server to identify the added candidates
  signallingTimedOut: boolean;
  stream: MediaStream | null;
  error: Error | null;
}
export const initialState: State = {
  webRtcState: "STOPPED",
  sdpOffer: null,
  iceCandidates: {},
  signallingTimedOut: false,
  stream: null,
  error: null,
};

export const reducer: React.Reducer<State, Action> = (state, action) => {
  switch (action.type) {
    case "SIGNALLING_START":
      return {
        ...state,
        webRtcState: "SIGNALLING",
        stream: null,
        error: null,
        signallingTimedOut: false,
      };
    case "SIGNALLING_TIMEOUT":
      return {
        ...state,
        signallingTimedOut: true,
      };
    case "SET_STREAM":
      return {
        ...state,
        stream: action.stream,
      };
    case "SET_OFFER":
      return {
        ...state,
        sdpOffer: action.offer,
      };
    case "ADD_ICE_CANDIDATE": {
      const uniqueId = Math.random().toString(36).substring(2, 15);
      return {
        ...state,
        iceCandidates: {
          ...state.iceCandidates,
          [uniqueId]: action.candidate,
        },
      };
    }
    case "STOPPING":
      return {
        ...state,
        webRtcState: "STOPPING",
        sdpOffer: null,
        iceCandidates: {},
      };
    case "STOPPED":
      return {
        ...state,
        webRtcState: "STOPPED",
        sdpOffer: null,
        iceCandidates: {},
        stream: null,
      };
    case "START_PLAYING":
      return {
        ...state,
        webRtcState: "PLAYING",
        sdpOffer: null,
        iceCandidates: {},
      };
    case "SET_OFFER_ERROR":
      return {
        ...state,
        webRtcState: "STOPPED",
        sdpOffer: null,
        iceCandidates: {},
        error: action.error,
      };
    case "PROCESS_ANSWER_ERROR":
      return {
        ...state,
        webRtcState: "STOPPED",
        sdpOffer: null,
        iceCandidates: {},
        error: action.error,
      };
    case "ERROR":
      return {
        ...state,
        webRtcState: "STOPPED",
        sdpOffer: null,
        iceCandidates: {},
        error: action.error,
      };
  }
};

export const connectReducer = (
  onComponentValueChange: (newComponentValue: ComponentValue) => void,
): React.Reducer<State, Action> => {
  const connectedReducer: React.Reducer<State, Action> = (state, action) => {
    const nextState = reducer(state, action);

    const nextPlaying = nextState.webRtcState === "PLAYING";
    const prevPlaying = state.webRtcState === "PLAYING";
    const playingChanged = nextPlaying !== prevPlaying;

    const nextSdpOffer = nextState.sdpOffer;
    const prevSdpOffer = state.sdpOffer;
    const sdpOfferChanged = nextSdpOffer !== prevSdpOffer;

    const nextIceCandidates = nextState.iceCandidates;
    const prevIceCandidates = state.iceCandidates;
    const iceCandidatesChanged = Object.keys(nextIceCandidates).length !== Object.keys(prevIceCandidates).length;

    if (playingChanged || sdpOfferChanged || iceCandidatesChanged) {
      const serializedIceCandidates = Object.fromEntries(
        Object.entries(nextIceCandidates).map(([key, value]) => [key, value.toJSON()])
      );

      const componentValue = {
        playing: nextPlaying,
        sdpOffer: nextSdpOffer ? nextSdpOffer.toJSON() : "", // `Streamlit.setComponentValue` cannot "unset" the field by passing null or undefined, so here an empty string is set instead when `sdpOffer` is undefined. // TODO: Create an issue
        iceCandidates: serializedIceCandidates,
      } satisfies ComponentValue;
      console.debug("set component value", componentValue);
      onComponentValueChange(componentValue);
    }

    return nextState;
  };

  return connectedReducer;
};
