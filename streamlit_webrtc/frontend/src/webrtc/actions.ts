interface ActionBase {
  type: string;
}
interface SignallingStartAction extends ActionBase {
  type: "SIGNALLING_START";
}
interface StreamSetAction extends ActionBase {
  type: "SET_STREAM";
  stream: MediaStream;
}
interface SetOfferAction extends ActionBase {
  type: "SET_OFFER";
  offer: RTCSessionDescription;
}
interface AddIceCandidateAction extends ActionBase {
  type: "ADD_ICE_CANDIDATE";
  candidate: RTCIceCandidate;
}
interface StoppingAction extends ActionBase {
  type: "STOPPING";
}
interface StoppedAction extends ActionBase {
  type: "STOPPED";
}
interface StartPlayingAction extends ActionBase {
  type: "START_PLAYING";
}
interface SetOfferErrorAction extends ActionBase {
  type: "SET_OFFER_ERROR";
  error: Error;
}
interface ProcessAnswerErrorAction extends ActionBase {
  type: "PROCESS_ANSWER_ERROR";
  error: Error;
}
interface ErrorAction extends ActionBase {
  type: "ERROR";
  error: Error;
}
export type Action =
  | SignallingStartAction
  | StreamSetAction
  | SetOfferAction
  | AddIceCandidateAction
  | StoppingAction
  | StoppedAction
  | StartPlayingAction
  | SetOfferErrorAction
  | ProcessAnswerErrorAction
  | ErrorAction;
