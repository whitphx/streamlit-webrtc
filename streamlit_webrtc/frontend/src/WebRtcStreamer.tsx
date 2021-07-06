import {
  Streamlit,
  StreamlitComponentBase,
  withStreamlitConnection,
  ComponentProps,
} from "streamlit-component-lib";
import React, { ReactNode } from "react";
import Box from "@material-ui/core/Box";
import Button from "@material-ui/core/Button";
import Alert from "@material-ui/lab/Alert";
import DeviceSelector from "./DeviceSelector";
import ThemeProvider from "./ThemeProvider";
import MediaStreamPlayer from "./MediaStreamPlayer";
import Placeholder from "./Placeholder";
import { compileMediaConstraints, getMediaUsage } from "./media-constraint";

type WebRtcMode = "RECVONLY" | "SENDONLY" | "SENDRECV";
const isWebRtcMode = (val: unknown): val is WebRtcMode =>
  val === "RECVONLY" || val === "SENDONLY" || val === "SENDRECV";
const isReceivable = (mode: WebRtcMode): boolean =>
  mode === "SENDRECV" || mode === "RECVONLY";
const isTransmittable = (mode: WebRtcMode): boolean =>
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

interface State {
  webRtcState: WebRtcState;
  sdpOffer: RTCSessionDescription | null;
  signallingTimedOut: boolean;
  videoInput: MediaDeviceInfo | null;
  audioInput: MediaDeviceInfo | null;
  stream: MediaStream | null;
  error: Error | null;
}

const SIGNALLING_TIMEOUT = 10 * 1000;

class WebRtcStreamer extends StreamlitComponentBase<State> {
  private pc: RTCPeerConnection | undefined;
  private signallingTimer: NodeJS.Timeout | undefined;

  constructor(props: ComponentProps) {
    super(props);

    this.state = {
      webRtcState: "STOPPED",
      sdpOffer: null,
      signallingTimedOut: false,
      videoInput: null,
      audioInput: null,
      stream: null,
      error: null,
    };
  }

  private processAnswerInner = async (
    pc: RTCPeerConnection,
    sdpAnswerJson: string
  ): Promise<void> => {
    const sdpAnswer = JSON.parse(sdpAnswerJson);
    console.log("Receive answer sdpOffer", sdpAnswer);
    await pc.setRemoteDescription(sdpAnswer);
    console.log("Remote description is set");
  };

  private processAnswer = (
    pc: RTCPeerConnection,
    sdpAnswerJson: string
  ): void => {
    this.processAnswerInner(pc, sdpAnswerJson)
      .then(() => {
        if (this.signallingTimer) {
          clearTimeout(this.signallingTimer);
        }
        this.setState({
          webRtcState: "PLAYING",
          sdpOffer: null,
        });
      })
      .catch((error) => {
        this.setState({ error });
        this.stop();
      });
  };

  private startInner = async () => {
    const mode = this.props.args["mode"];
    if (!isWebRtcMode(mode)) {
      throw new Error(`Invalid mode ${mode}`);
    }

    this.setState({
      webRtcState: "SIGNALLING",
      stream: null,
      error: null,
    });

    const config: RTCConfiguration =
      this.props.args.settings?.rtc_configuration || {};
    console.log("RTCConfiguration:", config);
    const pc = new RTCPeerConnection(config);

    // Connect received audio / video to DOM elements
    if (mode === "SENDRECV" || mode === "RECVONLY") {
      pc.addEventListener("track", (evt) => {
        const stream = evt.streams[0]; // TODO: Handle multiple streams
        this.setState({
          stream,
        });
      });
    }

    // Set up transceivers
    if (mode === "SENDRECV" || mode === "SENDONLY") {
      const constraints = compileMediaConstraints(
        this.props.args.settings?.media_stream_constraints,
        this.state.videoInput?.deviceId,
        this.state.audioInput?.deviceId
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

    this.pc = pc;

    await setupOffer(pc).then((offer) => {
      if (offer == null) {
        throw new Error("Failed to create an offer SDP");
      }

      this.setState({
        sdpOffer: offer,
      });
    });
  };

  private start = (): void => {
    if (this.state.webRtcState !== "STOPPED") {
      return;
    }

    this.setState({ signallingTimedOut: false });
    this.signallingTimer = setTimeout(() => {
      this.setState({ signallingTimedOut: true });
    }, SIGNALLING_TIMEOUT);

    this.startInner().catch((error) =>
      this.setState({ webRtcState: "STOPPED", sdpOffer: null, error })
    );
  };

  private stopInner = async (): Promise<void> => {
    if (this.state.webRtcState === "STOPPING") {
      return;
    }

    const pc = this.pc;
    this.pc = undefined;

    this.setState({ webRtcState: "STOPPING", sdpOffer: null });

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
    return new Promise((resolve) => {
      setTimeout(() => {
        pc.close();
        resolve();
      }, 500);
    });
  };

  private stop = () => {
    this.stopInner()
      .catch((error) => this.setState({ error }))
      .finally(() => {
        this.setState({
          webRtcState: "STOPPED",
          sdpOffer: null,
          stream: null,
        });
      });
  };

  private reconcilePlayingState = () => {
    const desiredPlayingState = this.props.args["desired_playing_state"];
    if (desiredPlayingState != null) {
      if (
        desiredPlayingState === true &&
        this.state.webRtcState === "STOPPED"
      ) {
        this.start();
      } else if (
        desiredPlayingState === false &&
        (this.state.webRtcState === "SIGNALLING" ||
          this.state.webRtcState === "PLAYING")
      ) {
        this.stop();
      }
    }
  };

  private reconcileComponentValue = (prevState: State) => {
    if (this.state === prevState) {
      return;
    }

    const playing = this.state.webRtcState === "PLAYING";
    const prevPlaying = prevState.webRtcState === "PLAYING";
    const playingChanged = playing !== prevPlaying;

    const sdpOffer = this.state.sdpOffer;
    const prevSdpOffer = prevState.sdpOffer;
    const sdpOfferChanged = sdpOffer !== prevSdpOffer;

    if (playingChanged || sdpOfferChanged) {
      if (sdpOffer) {
        console.log("Send SDP offer", sdpOffer);
      }
      Streamlit.setComponentValue({
        playing,
        sdpOffer: sdpOffer ? sdpOffer.toJSON() : "", // `Streamlit.setComponentValue` cannot "unset" the field by passing null or undefined, so here an empty string is set instead when `sdpOffer` is undefined. // TODO: Create an issue
      });
    }
  };

  public componentDidMount() {
    super.componentDidMount();

    this.reconcilePlayingState();
  }

  // @ts-ignore  // TODO: Fix the base class definition
  public componentDidUpdate(prevProps: ComponentProps, prevState: State) {
    super.componentDidUpdate();

    this.reconcilePlayingState();

    this.reconcileComponentValue(prevState);

    if (this.pc == null) {
      return;
    }
    const pc = this.pc;
    if (pc.remoteDescription == null) {
      const sdpAnswerJson = this.props.args["sdp_answer_json"];
      const prevSdpAnswerJson = prevProps.args["sdp_answer_json"];
      const sdpAnswerJsonChanged = sdpAnswerJson !== prevSdpAnswerJson;
      if (sdpAnswerJsonChanged) {
        if (sdpAnswerJson && this.state.webRtcState === "SIGNALLING") {
          this.processAnswer(pc, sdpAnswerJson);
        }
      }
    }
  }

  private handleDeviceSelect = (
    video: MediaDeviceInfo | null,
    audio: MediaDeviceInfo | null
  ) => {
    this.setState({ videoInput: video, audioInput: audio });
  };

  public render = (): ReactNode => {
    const desiredPlayingState = this.props.args["desired_playing_state"];
    const buttonDisabled =
      this.props.disabled ||
      (this.state.webRtcState === "SIGNALLING" &&
        !this.state.signallingTimedOut) || // Users can click the stop button after signalling timed out.
      this.state.webRtcState === "STOPPING" ||
      desiredPlayingState != null;
    const mode = this.props.args["mode"];
    const { videoEnabled, audioEnabled } = getMediaUsage(
      this.props.args.settings?.media_stream_constraints
    );
    const receivable = isWebRtcMode(mode) && isReceivable(mode);
    const transmittable = isWebRtcMode(mode) && isTransmittable(mode);

    return (
      <ThemeProvider theme={this.props.theme}>
        <Box>
          {this.state.error && (
            <Alert severity="error">
              {this.state.error.name}: {this.state.error.message}
            </Alert>
          )}
          <Box py={1}>
            {this.state.stream ? (
              <MediaStreamPlayer stream={this.state.stream} />
            ) : (
              receivable && (
                <Placeholder
                  loading={this.state.webRtcState === "SIGNALLING"}
                />
              )
            )}
          </Box>
          <Box display="flex" justifyContent="space-between">
            {this.state.webRtcState === "PLAYING" ||
            this.state.webRtcState === "SIGNALLING" ? (
              <Button
                variant="contained"
                onClick={this.stop}
                disabled={buttonDisabled}
              >
                Stop
              </Button>
            ) : (
              <Button
                variant="contained"
                color="primary"
                onClick={this.start}
                disabled={buttonDisabled}
              >
                Start
              </Button>
            )}
            {transmittable && (
              <DeviceSelector
                videoEnabled={videoEnabled}
                audioEnabled={audioEnabled}
                onSelect={this.handleDeviceSelect}
                value={{
                  video: this.state.videoInput,
                  audio: this.state.audioInput,
                }}
              />
            )}
          </Box>
        </Box>
      </ThemeProvider>
    );
  };
}

// "withStreamlitConnection" is a wrapper function. It bootstraps the
// connection between your component and the Streamlit app, and handles
// passing arguments from Python -> Component.
//
// You don't need to edit withStreamlitConnection (but you're welcome to!).
export default withStreamlitConnection(WebRtcStreamer);
