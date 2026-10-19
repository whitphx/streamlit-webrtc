import {
  useReducer,
  useCallback,
  useRef,
  useEffect,
  useMemo,
  type RefObject,
} from "react";
import { dequal } from "dequal/lite";
import { ComponentValue } from "../component-value";
import { connectReducer, initialState } from "./reducer";
import { useUniqueId } from "./use-unique-id";
import { openInputMediaStream } from "./open-input-media-stream";
import { switchInputDevice, type InputDeviceKind } from "./switch-input-device";
import {
  FrontendScriptError,
  loadFrontendScript,
  setUpFrontendScript,
  type FrontendScriptHandle,
  type FrontendScriptMedia,
} from "./frontend-script";

export type { InputDeviceKind };

export interface DataChannelSpec {
  label: string;
  id: number;
  ordered?: boolean;
  maxPacketLifeTime?: number;
  maxRetransmits?: number;
  protocol?: string;
}

export type WebRtcMode = "RECVONLY" | "SENDONLY" | "SENDRECV";
export const isWebRtcMode = (val: unknown): val is WebRtcMode =>
  val === "RECVONLY" || val === "SENDONLY" || val === "SENDRECV";
export const isReceivable = (mode: WebRtcMode): boolean =>
  mode === "SENDRECV" || mode === "RECVONLY";
export const isTransmittable = (mode: WebRtcMode): boolean =>
  mode === "SENDRECV" || mode === "SENDONLY";

export const useWebRtc = (
  props: {
    mode: WebRtcMode;
    desiredPlayingState: boolean | undefined;
    sdpAnswerJson: string | undefined;
    rtcConfiguration: RTCConfiguration | undefined;
    mediaStreamConstraints: MediaStreamConstraints | undefined;
    sendbackVideo: boolean;
    sendbackAudio: boolean;
    dataChannels?: DataChannelSpec[];
    frontendScript?: string | null;
    frontendData?: unknown;
    frontendScriptRootRef?: RefObject<HTMLDivElement>;
    frontendScriptMediaRef?: RefObject<FrontendScriptMedia>;
  },
  videoDeviceIdRequest: MediaDeviceInfo["deviceId"] | undefined,
  audioDeviceIdRequest: MediaDeviceInfo["deviceId"] | undefined,
  onComponentValueChange: (newComponentValue: ComponentValue) => void,
  onDevicesOpened: (openedDeviceIds: {
    video?: string;
    audio?: string;
  }) => void,
  onDevicesUnavailable: (unavailableDeviceKinds: InputDeviceKind[]) => void,
) => {
  // Initialize component value
  useEffect(() => {
    return onComponentValueChange({
      playing: false,
      sdpOffer: "",
      iceCandidates: {},
    });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const pcRef = useRef<RTCPeerConnection>();
  // Bumped by every start() and stop(), so that a start() resuming from one
  // of its awaits can tell that its session has been stopped or replaced.
  const sessionRef = useRef(0);
  const frontendScriptRootOwnerRef = useRef<number>();
  const frontendScriptHandleRef = useRef<FrontendScriptHandle>();
  const deliveredFrontendDataRef = useRef<unknown>();
  const frontendDataRef = useRef(props.frontendData);
  frontendDataRef.current = props.frontendData;
  const reducer = useMemo(
    () => connectReducer(onComponentValueChange),
    [onComponentValueChange],
  );
  const [state, dispatch] = useReducer(reducer, initialState);

  const uniqueIdGenerator = useUniqueId();

  const stop = useCallback(() => {
    const stopInner = async () => {
      if (state.webRtcState === "STOPPING") {
        return;
      }

      const pc = pcRef.current;
      pcRef.current = undefined;
      sessionRef.current++;

      dispatch({ type: "STOPPING" });

      if (pc == null) {
        return;
      }

      const frontendScriptHandle = frontendScriptHandleRef.current;
      frontendScriptHandleRef.current = undefined;
      try {
        frontendScriptHandle?.cleanup?.();
      } catch (error) {
        console.error("frontend_script cleanup failed", error);
      }
      props.frontendScriptRootRef?.current?.replaceChildren();

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
  }, [state.webRtcState, props.frontendScriptRootRef]);

  const stopRef = useRef(stop);
  stopRef.current = stop;

  const inputMediaStreamRef = useRef(state.inputMediaStream);
  inputMediaStreamRef.current = state.inputMediaStream;

  const updateInputDevice = useCallback(
    async (
      kind: InputDeviceKind,
      deviceId: MediaDeviceInfo["deviceId"],
    ): Promise<void> => {
      const pc = pcRef.current;
      const inputMediaStream = state.inputMediaStream;
      if (pc == null || inputMediaStream == null) {
        throw new Error(
          "Cannot switch input device without an active WebRTC input stream",
        );
      }
      await switchInputDevice(
        pc,
        inputMediaStream,
        props.mediaStreamConstraints,
        kind,
        deviceId,
      );
      // `getUserMedia` can sit on a permission prompt for as long as the user
      // takes, long enough for the connection to be stopped and started again.
      // Publishing the stream this switch was made against would then put a
      // stopped one back in place of the one now playing.
      if (
        pcRef.current !== pc ||
        inputMediaStreamRef.current !== inputMediaStream
      ) {
        return;
      }
      dispatch({
        type: "SET_INPUT_MEDIA_STREAM",
        inputMediaStream,
      });
    },
    [props.mediaStreamConstraints, state.inputMediaStream],
  );

  const start = useCallback((): Promise<void> => {
    if (state.webRtcState !== "STOPPED") {
      return Promise.reject(new Error("WebRTC is already started"));
    }

    const session = ++sessionRef.current;
    const isSuperseded = () => sessionRef.current !== session;

    const startInner = async () => {
      // Dispatched before the first await so that the state leaves STOPPED,
      // which shows Stop and blocks a second start(), for the whole setup.
      dispatch({ type: "SIGNALLING_START" });

      // Load the `webrtc-adapter` shims before any `RTCPeerConnection` /
      // `getUserMedia` call below. The import is dynamic so the polyfill is
      // split into its own chunk and not paid for on initial render.
      await import("webrtc-adapter");

      const frontendScriptSetup = props.frontendScript
        ? await loadFrontendScript(props.frontendScript).catch((error) => {
            console.error("frontend_script failed to load", error);
            throw new FrontendScriptError(error);
          })
        : undefined;
      if (isSuperseded()) {
        return;
      }

      uniqueIdGenerator.reset();

      const mode = props.mode;

      const config: RTCConfiguration = props.rtcConfiguration || {};
      console.debug("RTCConfiguration:", config);
      const pc = new RTCPeerConnection(config);

      let openedInputMediaStream: MediaStream | null = null;
      let frontendScriptHandle: FrontendScriptHandle | undefined;
      // Until pcRef holds the connection, stop() cannot reach what this
      // session has opened, so every exit before that goes through here.
      const release = () => {
        try {
          frontendScriptHandle?.cleanup?.();
        } catch (error) {
          console.error("frontend_script cleanup failed", error);
        }
        // A session stopped during its setup can finish after the next one
        // has started drawing into the same root.
        if (frontendScriptRootOwnerRef.current === session) {
          frontendScriptRootOwnerRef.current = undefined;
          props.frontendScriptRootRef?.current?.replaceChildren();
        }
        openedInputMediaStream?.getTracks().forEach((track) => track.stop());
        pc.close();
      };

      try {
        // Connect received audio / video to DOM elements
        if (mode === "SENDRECV" || mode === "RECVONLY") {
          pc.addEventListener("track", (evt) => {
            const outputMediaStream = evt.streams[0]; // TODO: Handle multiple streams
            dispatch({ type: "SET_OUTPUT_MEDIA_STREAM", outputMediaStream });
          });
        }

        // Set up transceivers
        if (mode === "SENDRECV" || mode === "SENDONLY") {
          const inputMediaStream = await openInputMediaStream(
            props.mediaStreamConstraints,
            videoDeviceIdRequest,
            audioDeviceIdRequest,
            onDevicesUnavailable,
          );
          openedInputMediaStream = inputMediaStream;
          if (isSuperseded()) {
            release();
            return;
          }

          if (inputMediaStream != null) {
            const openedDeviceIds: {
              video?: MediaDeviceInfo["deviceId"];
              audio?: MediaDeviceInfo["deviceId"];
            } = {};
            dispatch({ type: "SET_INPUT_MEDIA_STREAM", inputMediaStream });
            inputMediaStream.getTracks().forEach((track) => {
              pc.addTrack(track, inputMediaStream);

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
          } else if (mode === "SENDRECV") {
            // When the local capture is one-sided (e.g. audio-only), the SDP
            // offer ends up with only an audio m-section and the server has
            // nowhere to attach a video sender. Add an explicit recvonly
            // transceiver for any kind we are not sending so the server can
            // still send back a track of that kind (driven by `source_*`).
            // Gated on the corresponding `sendback_*` so opting out skips
            // the extra m-section.
            const localKinds = new Set(
              pc
                .getTransceivers()
                .map((t) => t.sender.track?.kind)
                .filter(
                  (k): k is "audio" | "video" => k === "audio" || k === "video",
                ),
            );
            if (props.sendbackVideo && !localKinds.has("video")) {
              pc.addTransceiver("video", { direction: "recvonly" });
            }
            if (props.sendbackAudio && !localKinds.has("audio")) {
              pc.addTransceiver("audio", { direction: "recvonly" });
            }
          }
        } else if (mode === "RECVONLY") {
          pc.addTransceiver("video", { direction: "recvonly" });
          pc.addTransceiver("audio", { direction: "recvonly" });
        }
        console.debug("transceivers", pc.getTransceivers());

        // Created before the offer so that it negotiates the SCTP transport.
        // See `compile_data_channel_specs()` for why they are `negotiated`.
        const channels = Object.fromEntries(
          (props.dataChannels ?? []).map(({ label, ...init }) => [
            label,
            pc.createDataChannel(label, { ...init, negotiated: true }),
          ]),
        );

        if (frontendScriptSetup) {
          const root = props.frontendScriptRootRef?.current;
          if (root == null) {
            throw new Error("No root element for frontend_script");
          }
          const { video, audio } = props.frontendScriptMediaRef?.current ?? {};
          const data = frontendDataRef.current;
          frontendScriptRootOwnerRef.current = session;
          // A session stopped during its setup leaves whatever it had drawn
          // so far, since its release must not empty a root it lost.
          root.replaceChildren();
          try {
            frontendScriptHandle = await setUpFrontendScript(
              frontendScriptSetup,
              {
                pc,
                channels,
                root,
                media: { ...(video && { video }), ...(audio && { audio }) },
                data,
              },
            );
          } catch (error) {
            console.error("frontend_script setup failed", error);
            throw new FrontendScriptError(error);
          }
          if (isSuperseded()) {
            release();
            return;
          }
          frontendScriptHandleRef.current = frontendScriptHandle;
          deliveredFrontendDataRef.current = data;
        }

        pc.addEventListener("connectionstatechange", () => {
          console.debug("connectionstatechange", pc.connectionState);
          if (pc.connectionState === "connected") {
            dispatch({ type: "START_PLAYING" });
          } else if (
            pc.connectionState === "disconnected" ||
            pc.connectionState === "closed" ||
            pc.connectionState === "failed"
          ) {
            stopRef.current();
          }
        });

        pcRef.current = pc;
      } catch (error) {
        release();
        throw error;
      }

      // Trickle ICE
      pc.addEventListener("icecandidate", (evt) => {
        if (evt.candidate) {
          console.debug("icecandidate", evt.candidate);
          const id = uniqueIdGenerator.get(); // NOTE: Generate the ID here to ensure it is uniquely bound to the candidate. It can be violated if it's generated in the reducer.
          dispatch({ type: "ADD_ICE_CANDIDATE", id, candidate: evt.candidate });
        }
      });

      pc.createOffer()
        .then((offer) =>
          pc.setLocalDescription(offer).then(() => {
            if (isSuperseded()) {
              return;
            }
            const localDescription = pc.localDescription;
            if (localDescription == null) {
              throw new Error("Failed to create an offer SDP");
            }
            dispatch({ type: "SET_OFFER", offer: localDescription });
          }),
        )
        .catch((error) => {
          if (isSuperseded()) {
            return;
          }
          dispatch({ type: "SET_OFFER_ERROR", error });
        });
    };

    return startInner().catch((error) => {
      // A stopped or replaced session has no UI left to report to,
      // and an ERROR would mark the session now running as stopped.
      if (isSuperseded()) {
        console.error(error);
        return;
      }
      dispatch({
        type: "ERROR",
        error,
      });
    });
  }, [
    audioDeviceIdRequest,
    videoDeviceIdRequest,
    props.mediaStreamConstraints,
    props.mode,
    props.rtcConfiguration,
    props.sendbackVideo,
    props.sendbackAudio,
    props.dataChannels,
    props.frontendScript,
    props.frontendScriptRootRef,
    props.frontendScriptMediaRef,
    state.webRtcState,
    onDevicesOpened,
    onDevicesUnavailable,
    uniqueIdGenerator,
  ]);

  // Runs after every render rather than when `frontendData` changes: each
  // rerun brings a new object even when the data is equal, and the data can
  // change while the script's setup is still running.
  useEffect(() => {
    const update = frontendScriptHandleRef.current?.update;
    const data = frontendDataRef.current;
    if (update == null || dequal(data, deliveredFrontendDataRef.current)) {
      return;
    }
    deliveredFrontendDataRef.current = data;
    try {
      update(data);
    } catch (error) {
      console.error("frontend_script update failed", error);
    }
  });

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
        console.debug("Receive answer SDP", sdpAnswer);
        pc.setRemoteDescription(sdpAnswer).catch((error) => {
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
    updateInputDevice,
    state,
  };
};
