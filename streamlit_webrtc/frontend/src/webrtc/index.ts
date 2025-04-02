import { useReducer, useCallback, useRef, useEffect, useMemo } from "react";
import { compileMediaConstraints } from "../media-constraint";
import { ComponentValue } from "../component-value";
import { connectReducer, initialState } from "./reducer";

export type WebRtcMode = "RECVONLY" | "SENDONLY" | "SENDRECV";
export const isWebRtcMode = (val: unknown): val is WebRtcMode =>
  val === "RECVONLY" || val === "SENDONLY" || val === "SENDRECV";
export const isReceivable = (mode: WebRtcMode): boolean =>
  mode === "SENDRECV" || mode === "RECVONLY";
export const isTransmittable = (mode: WebRtcMode): boolean =>
  mode === "SENDRECV" || mode === "SENDONLY";

const SIGNALLING_TIMEOUT = 3 * 1000;

export const useWebRtc = (
  props: {
    mode: WebRtcMode;
    desiredPlayingState: boolean | undefined;
    sdpAnswerJson: string | undefined;
    rtcConfiguration: RTCConfiguration | undefined;
    mediaStreamConstraints: MediaStreamConstraints | undefined;
  },
  videoDeviceIdRequest: MediaDeviceInfo["deviceId"] | undefined,
  audioDeviceIdRequest: MediaDeviceInfo["deviceId"] | undefined,
  onComponentValueChange: (newComponentValue: ComponentValue) => void,
  onDevicesOpened: (openedDeviceIds: {
    video?: string;
    audio?: string;
  }) => void,
) => {
  // Initialize component value
  useEffect(() => {
    return onComponentValueChange({
      playing: false,
      sdpOffer: "",
    });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const signallingTimerRef = useRef<NodeJS.Timeout>();
  const pcRef = useRef<RTCPeerConnection>();
  const reducer = useMemo(
    () => connectReducer(onComponentValueChange),
    [onComponentValueChange],
  );
  const [state, dispatch] = useReducer(reducer, initialState);

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

  const stopRef = useRef(stop);
  stopRef.current = stop;

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
      console.debug("RTCConfiguration:", config);
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
          videoDeviceIdRequest,
          audioDeviceIdRequest,
        );
        console.debug("MediaStreamConstraints:", constraints);

        if (constraints.audio || constraints.video) {
          if (navigator.mediaDevices == null) {
            // Ref: https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia#privacy_and_security
            // > A secure context is, in short, a page loaded using HTTPS or the file:/// URL scheme, or a page loaded from localhost.
            throw new Error(
              "navigator.mediaDevices is undefined. It seems the current document is not loaded securely.",
            );
          }
          if (navigator.mediaDevices.getUserMedia == null) {
            throw new Error("getUserMedia is not implemented in this browser");
          }

          const openedDeviceIds: {
            video?: MediaDeviceInfo["deviceId"];
            audio?: MediaDeviceInfo["deviceId"];
          } = {};
          const stream = await navigator.mediaDevices.getUserMedia(constraints);
          stream.getTracks().forEach((track) => {
            pc.addTrack(track, stream);

            const kind = track.kind;
            if (kind !== "video" && kind !== "audio") {
              return;
            }
            const deviceId = track.getSettings().deviceId;
            if (deviceId == null) {
              return;
            }
            openedDeviceIds[kind] = deviceId;
          });
          if (Object.keys(openedDeviceIds).length > 0) {
            onDevicesOpened(openedDeviceIds);
          }
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
      console.debug("transceivers", pc.getTransceivers());

      pc.addEventListener("iceconnectionstatechange", () => {
        console.debug("iceconnectionstatechange", pc.iceConnectionState);
        if (
          pc.iceConnectionState === "disconnected" ||
          pc.iceConnectionState === "failed" ||
          pc.iceConnectionState === "closed"
        ) {
          stopRef.current();
        }
      });

      pcRef.current = pc;

      pc.addEventListener("icecandidate", (evt) => {
        if (evt.candidate) {
          console.debug("icecandidate", evt.candidate);
          dispatch({ type: "ADD_ICE_CANDIDATE", candidate: evt.candidate });
        }
      });

      pc.createOffer()
        .then((offer) =>
          pc.setLocalDescription(offer).then(() => {
            const localDescription = pc.localDescription;
            if (localDescription == null) {
              throw new Error("Failed to create an offer SDP");
            }
            dispatch({ type: "SET_OFFER", offer: localDescription });
          })
        )
        .catch((error) => {
          dispatch({ type: "SET_OFFER_ERROR", error });
        })
    };

    startInner().catch((error) =>
      dispatch({
        type: "ERROR",
        error,
      }),
    );
  }, [
    audioDeviceIdRequest,
    videoDeviceIdRequest,
    props.mediaStreamConstraints,
    props.mode,
    props.rtcConfiguration,
    state.webRtcState,
    onDevicesOpened,
  ]);

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
        console.debug("Receive answer sdpOffer", sdpAnswer);
        pc.setRemoteDescription(sdpAnswer)
          .then(() => {
            console.debug("Remote description is set");

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
