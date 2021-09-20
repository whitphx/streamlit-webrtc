interface ActionBase {
  type: string;
}
interface SignallingStartAction extends ActionBase {
  type: "SIGNALLING_START";
}
interface SignallingTimeoutAction extends ActionBase {
  type: "SIGNALLING_TIMEOUT";
}
interface StreamSetAction extends ActionBase {
  type: "SET_STREAM";
  stream: MediaStream;
}
interface SetOfferAction extends ActionBase {
  type: "SET_OFFER";
  offer: RTCSessionDescription;
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
  | SignallingTimeoutAction
  | StreamSetAction
  | SetOfferAction
  | StoppingAction
  | StoppedAction
  | StartPlayingAction
  | ProcessAnswerErrorAction
  | ErrorAction;
