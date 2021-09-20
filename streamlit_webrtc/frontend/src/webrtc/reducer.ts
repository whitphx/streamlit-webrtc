import { ComponentValue } from "../component-value";
import { Action } from "./actions";

export type WebRtcState = "STOPPED" | "SIGNALLING" | "PLAYING" | "STOPPING";
export interface State {
  webRtcState: WebRtcState;
  sdpOffer: RTCSessionDescription | null;
  signallingTimedOut: boolean;
  stream: MediaStream | null;
  error: Error | null;
}
export const initialState: State = {
  webRtcState: "STOPPED",
  sdpOffer: null,
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
    case "STOPPING":
      return {
        ...state,
        webRtcState: "STOPPING",
        sdpOffer: null,
      };
    case "STOPPED":
      return {
        ...state,
        webRtcState: "STOPPED",
        sdpOffer: null,
        stream: null,
      };
    case "START_PLAYING":
      return {
        ...state,
        webRtcState: "PLAYING",
        sdpOffer: null,
      };
    case "PROCESS_ANSWER_ERROR":
      return {
        ...state,
        error: action.error,
      };
    case "ERROR":
      return {
        ...state,
        webRtcState: "STOPPED",
        sdpOffer: null,
        error: action.error,
      };
  }
};

export const connectReducer = (
  onComponentValueChange: (newComponentValue: ComponentValue) => void
): React.Reducer<State, Action> => {
  const connectedReducer: React.Reducer<State, Action> = (state, action) => {
    const nextState = reducer(state, action);

    const nextPlaying = nextState.webRtcState === "PLAYING";
    const prevPlaying = state.webRtcState === "PLAYING";
    const playingChanged = nextPlaying !== prevPlaying;

    const nextSdpOffer = nextState.sdpOffer;
    const prevSdpOffer = state.sdpOffer;
    const sdpOfferChanged = nextSdpOffer !== prevSdpOffer;

    if (playingChanged || sdpOfferChanged) {
      if (prevSdpOffer) {
        console.log("Send SDP offer", prevSdpOffer);
      }
      onComponentValueChange({
        playing: nextPlaying,
        sdpOffer: nextSdpOffer ? nextSdpOffer.toJSON() : "", // `Streamlit.setComponentValue` cannot "unset" the field by passing null or undefined, so here an empty string is set instead when `sdpOffer` is undefined. // TODO: Create an issue
      });
    }

    return nextState;
  };

  return connectedReducer;
};
