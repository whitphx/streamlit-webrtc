import React, { useReducer, useCallback, useRef, useEffect } from "react";
import { compileMediaConstraints } from "./media-constraint";
import { setComponentValue } from "./component-value";

export type WebRtcMode = "RECVONLY" | "SENDONLY" | "SENDRECV";
export const isWebRtcMode = (val: unknown): val is WebRtcMode =>
  val === "RECVONLY" || val === "SENDONLY" || val === "SENDRECV";
export const isReceivable = (mode: WebRtcMode): boolean =>
  mode === "SENDRECV" || mode === "RECVONLY";
export const isTransmittable = (mode: WebRtcMode): boolean =>
  mode === "SENDRECV" || mode === "SENDONLY";

const setupOffer = (
  pc: RTCPeerConnection
): Promise<RTCSessionDescription | null> => {
  return pc
    .createOffer()
    .then((offer) => {
      console.log("Created offer:", offer);
      return pc.setLocalDescription(offer);
    })
    .then(() => {
      console.log("Wait for ICE gethering...");
      // Wait for ICE gathering to complete
      return new Promise<void>((resolve) => {
        if (pc.iceGatheringState === "complete") {
          resolve();
        } else {
          const checkState = () => {
            if (pc.iceGatheringState === "complete") {
              pc.removeEventListener("icegatheringstatechange", checkState);
              resolve();
            }
          };
          pc.addEventListener("icegatheringstatechange", checkState);
        }
      });
    })
    .then(() => {
      const offer = pc.localDescription;
      return offer;
    })
    .catch((err) => {
      console.error(err);
      throw err;
    });
};

type WebRtcState = "STOPPED" | "SIGNALLING" | "PLAYING" | "STOPPING";
const SIGNALLING_TIMEOUT = 10 * 1000;
interface State {
  webRtcState: WebRtcState;
  sdpOffer: RTCSessionDescription | null;
  signallingTimedOut: boolean;
  stream: MediaStream | null;
  error: Error | null;
}
const initialState: State = {
  webRtcState: "STOPPED",
  sdpOffer: null,
  signallingTimedOut: false,
  stream: null,
  error: null,
};
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
type Action =
  | SignallingStartAction
  | SignallingTimeoutAction
  | StreamSetAction
  | SetOfferAction
  | StoppingAction
  | StoppedAction
  | StartPlayingAction
  | ProcessAnswerErrorAction
  | ErrorAction;
const reducer: React.Reducer<State, Action> = (state, action) => {
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
    setComponentValue({
      playing: nextPlaying,
      sdpOffer: nextSdpOffer ? nextSdpOffer.toJSON() : "", // `Streamlit.setComponentValue` cannot "unset" the field by passing null or undefined, so here an empty string is set instead when `sdpOffer` is undefined. // TODO: Create an issue
    });
  }

  return nextState;
};

export const useWebRtc = (
  props: {
    mode: WebRtcMode;
    desiredPlayingState: boolean | undefined;
    sdpAnswerJson: string | undefined;
    rtcConfiguration: RTCConfiguration | undefined;
    mediaStreamConstraints: MediaStreamConstraints | undefined;
  },
  videoInput: MediaDeviceInfo | null,
  audioInput: MediaDeviceInfo | null
) => {
  // Initialize component value
  useEffect(() => {
    return setComponentValue({
      playing: false,
      sdpOffer: "",
    });
  }, []);

  const signallingTimerRef = useRef<NodeJS.Timeout>();
  const pcRef = useRef<RTCPeerConnection>();
  const [state, dispatch] = useReducer(connectedReducer, initialState);

  const start = useCallback(() => {
    if (state.webRtcState !== "STOPPED") {
      return;
    }

    const startInner = async () => {
      dispatch({ type: "SIGNALLING_START" });
      signallingTimerRef.current = setTimeout(() => {
        dispatch({ type: "SIGNALLING_TIMEOUT" });
      }, SIGNALLING_TIMEOUT);

      const mode = props.mode;

      const config: RTCConfiguration = props.rtcConfiguration || {};
      console.log("RTCConfiguration:", config);
      const pc = new RTCPeerConnection(config);

      // Connect received audio / video to DOM elements
      if (mode === "SENDRECV" || mode === "RECVONLY") {
        pc.addEventListener("track", (evt) => {
          const stream = evt.streams[0]; // TODO: Handle multiple streams
          dispatch({ type: "SET_STREAM", stream });
        });
      }

      // Set up transceivers
      if (mode === "SENDRECV" || mode === "SENDONLY") {
        const constraints = compileMediaConstraints(
          props.mediaStreamConstraints,
          videoInput?.deviceId,
          audioInput?.deviceId
        );
        console.log("MediaStreamConstraints:", constraints);

        if (constraints.audio || constraints.video) {
          if (navigator.mediaDevices == null) {
            // Ref: https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia#privacy_and_security
            // > A secure context is, in short, a page loaded using HTTPS or the file:/// URL scheme, or a page loaded from localhost.
            throw new Error(
              "navigator.mediaDevices is undefined. It seems the current document is not loaded securely."
            );
          }
          if (navigator.mediaDevices.getUserMedia == null) {
            throw new Error("getUserMedia is not implemented in this browser");
          }

          const stream = await navigator.mediaDevices.getUserMedia(constraints);
          stream.getTracks().forEach((track) => {
            pc.addTrack(track, stream);
          });
        }

        if (mode === "SENDONLY") {
          for (const transceiver of pc.getTransceivers()) {
            transceiver.direction = "sendonly";
          }
        }
      } else if (mode === "RECVONLY") {
        pc.addTransceiver("video", { direction: "recvonly" });
        pc.addTransceiver("audio", { direction: "recvonly" });
      }

      console.log("transceivers", pc.getTransceivers());

      pcRef.current = pc;

      await setupOffer(pc).then((offer) => {
        if (offer == null) {
          throw new Error("Failed to create an offer SDP");
        }

        dispatch({ type: "SET_OFFER", offer });
      });
    };

    startInner().catch((error) =>
      dispatch({
        type: "ERROR",
        error,
      })
    );
  }, [
    audioInput?.deviceId,
    props.mediaStreamConstraints,
    props.mode,
    props.rtcConfiguration,
    state.webRtcState,
    videoInput?.deviceId,
  ]);

  const stop = useCallback(() => {
    const stopInner = async () => {
      if (state.webRtcState === "STOPPING") {
        return;
      }

      const pc = pcRef.current;
      pcRef.current = undefined;

      dispatch({ type: "STOPPING" });

      if (pc == null) {
        return;
      }

      // close transceivers
      if (pc.getTransceivers) {
        pc.getTransceivers().forEach(function (transceiver) {
          if (transceiver.stop) {
            transceiver.stop();
          }
        });
      }

      // close local audio / video
      pc.getSenders().forEach(function (sender) {
        sender.track?.stop();
      });

      // close peer connection
      return new Promise<void>((resolve) => {
        setTimeout(() => {
          pc.close();
          resolve();
        }, 500);
      });
    };

    stopInner()
      .catch((error) => dispatch({ type: "ERROR", error }))
      .finally(() => {
        dispatch({ type: "STOPPED" });
      });
  }, [state.webRtcState]);

  // processAnswer
  useEffect(() => {
    const pc = pcRef.current;
    if (pc == null) {
      return;
    }

    const sdpAnswerJson = props.sdpAnswerJson;
    if (pc.remoteDescription == null) {
      if (sdpAnswerJson && state.webRtcState === "SIGNALLING") {
        const sdpAnswer = JSON.parse(sdpAnswerJson);
        console.log("Receive answer sdpOffer", sdpAnswer);
        pc.setRemoteDescription(sdpAnswer)
          .then(() => {
            console.log("Remote description is set");

            if (signallingTimerRef.current) {
              clearTimeout(signallingTimerRef.current);
            }
            dispatch({ type: "START_PLAYING" });
          })
          .catch((error) => {
            dispatch({ type: "PROCESS_ANSWER_ERROR", error });
            stop();
          });
      }
    }
  }, [props.sdpAnswerJson, state.webRtcState, stop]);

  // reconcilePlayingState
  useEffect(() => {
    const desiredPlayingState = props.desiredPlayingState;
    if (desiredPlayingState != null) {
      if (desiredPlayingState === true && state.webRtcState === "STOPPED") {
        start();
      } else if (
        desiredPlayingState === false &&
        (state.webRtcState === "SIGNALLING" || state.webRtcState === "PLAYING")
      ) {
        stop();
      }
    }
  }, [props.desiredPlayingState, start, state.webRtcState, stop]);

  return {
    start,
    stop,
    state,
  };
};
