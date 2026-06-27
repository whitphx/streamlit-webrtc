interface ActionBase {
  type: string;
}
interface SignallingStartAction extends ActionBase {
  type: "SIGNALLING_START";
}
interface OutputMediaStreamSetAction extends ActionBase {
  type: "SET_OUTPUT_MEDIA_STREAM";
  outputMediaStream: MediaStream;
}
interface InputMediaStreamSetAction extends ActionBase {
  type: "SET_INPUT_MEDIA_STREAM";
  inputMediaStream: MediaStream;
}
interface SetOfferAction extends ActionBase {
  type: "SET_OFFER";
  offer: RTCSessionDescription;
}
interface AddIceCandidateAction extends ActionBase {
  type: "ADD_ICE_CANDIDATE";
  id: string;
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
  | OutputMediaStreamSetAction
  | InputMediaStreamSetAction
  | SetOfferAction
  | AddIceCandidateAction
  | StoppingAction
  | StoppedAction
  | StartPlayingAction
  | SetOfferErrorAction
  | ProcessAnswerErrorAction
  | ErrorAction;
