import { ComponentValue } from "../component-value";
import { Action } from "./actions";

export type WebRtcState = "STOPPED" | "SIGNALLING" | "PLAYING" | "STOPPING";
export interface State {
  webRtcState: WebRtcState;
  sdpOffer: RTCSessionDescription | null;
  iceCandidates: Record<string, RTCIceCandidate>; // key: candidate id for the server to identify the added candidates
  outputMediaStream: MediaStream | null;
  inputMediaStream: MediaStream | null;
  error: Error | null;
}
export const initialState: State = {
  webRtcState: "STOPPED",
  sdpOffer: null,
  iceCandidates: {},
  outputMediaStream: null,
  inputMediaStream: null,
  error: null,
};

export const reducer: React.Reducer<State, Action> = (state, action) => {
  switch (action.type) {
    case "SIGNALLING_START":
      return {
        ...state,
        webRtcState: "SIGNALLING",
        outputMediaStream: null,
        inputMediaStream: null,
        error: null,
      };
    case "SET_OUTPUT_MEDIA_STREAM":
      return {
        ...state,
        outputMediaStream: action.outputMediaStream,
      };
    case "SET_INPUT_MEDIA_STREAM":
      return {
        ...state,
        inputMediaStream: action.inputMediaStream,
      };
    case "SET_OFFER":
      return {
        ...state,
        sdpOffer: action.offer,
      };
    case "ADD_ICE_CANDIDATE": {
      return {
        ...state,
        iceCandidates: {
          ...state.iceCandidates,
          [action.id]: action.candidate,
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
        outputMediaStream: null,
        inputMediaStream: null,
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
        inputMediaStream: null,
        error: action.error,
      };
    case "PROCESS_ANSWER_ERROR":
      return {
        ...state,
        webRtcState: "STOPPED",
        sdpOffer: null,
        iceCandidates: {},
        inputMediaStream: null,
        error: action.error,
      };
    case "ERROR":
      return {
        ...state,
        webRtcState: "STOPPED",
        sdpOffer: null,
        iceCandidates: {},
        inputMediaStream: null,
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
    const iceCandidatesChanged =
      Object.keys(nextIceCandidates).length !==
      Object.keys(prevIceCandidates).length;

    if (playingChanged || sdpOfferChanged || iceCandidatesChanged) {
      const serializedIceCandidates = Object.fromEntries(
        Object.entries(nextIceCandidates).map(([key, value]) => [
          key,
          value.toJSON(),
        ]),
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
