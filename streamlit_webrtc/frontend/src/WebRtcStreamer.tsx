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

type WebRtcMode = "RECVONLY" | "SENDONLY" | "SENDRECV";
const isWebRtcMode = (val: unknown): val is WebRtcMode =>
  val === "RECVONLY" || val === "SENDONLY" || val === "SENDRECV";
const isReceivable = (mode: WebRtcMode): boolean =>
  mode === "SENDRECV" || mode === "RECVONLY";
const isTransmittable = (mode: WebRtcMode): boolean =>
  mode === "SENDRECV" || mode === "SENDONLY";

const getVideoAudioUsage = (
  args: any
): { useVideo: boolean; useAudio: boolean } => {
  const constraintsFromPython = args.settings?.media_stream_constraints;
  const useVideo = constraintsFromPython ? constraintsFromPython.video : true;
  const useAudio = constraintsFromPython ? constraintsFromPython.audio : true;

  return { useVideo, useAudio };
};

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

interface State {
  signaling: boolean;
  playing: boolean;
  stopping: boolean;
  videoInput: MediaDeviceInfo | null;
  audioInput: MediaDeviceInfo | null;
  stream: MediaStream | null;
  error: Error | null;
}

class WebRtcStreamer extends StreamlitComponentBase<State> {
  private pc: RTCPeerConnection | undefined;
  private videoRef: React.RefObject<HTMLVideoElement>;
  private audioRef: React.RefObject<HTMLAudioElement>;

  constructor(props: ComponentProps) {
    super(props);
    this.videoRef = React.createRef();
    this.audioRef = React.createRef();

    this.state = {
      signaling: false,
      playing: false,
      stopping: false,
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
  };

  private processAnswer = (
    pc: RTCPeerConnection,
    sdpAnswerJson: string
  ): void => {
    this.processAnswerInner(pc, sdpAnswerJson)
      .then(() => {
        console.log("Remote description is set");
      })
      .finally(() => this.setState({ signaling: false }));
  };

  private startInner = async () => {
    const mode = this.props.args["mode"];
    if (!isWebRtcMode(mode)) {
      throw new Error(`Invalid mode ${mode}`);
    }

    this.setState({
      signaling: true,
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
      const { useVideo, useAudio } = getVideoAudioUsage(this.props.args);
      const constraints: MediaStreamConstraints = {};
      if (useAudio) {
        constraints.audio = this.state.audioInput
          ? {
              deviceId: this.state.audioInput.deviceId,
            }
          : true;
      }
      if (useVideo) {
        constraints.video = this.state.videoInput
          ? {
              deviceId: this.state.videoInput.deviceId,
            }
          : true;
      }
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

    this.setState({ playing: true });

    console.log("transceivers", pc.getTransceivers());

    setupOffer(pc).then((offer) => {
      if (offer == null) {
        console.warn("Failed to create an offer SDP");
        return;
      }

      console.log("Send sdpOffer", offer.toJSON());
      Streamlit.setComponentValue({
        sdpOffer: offer.toJSON(),
        playing: true,
      });
    });
    this.pc = pc;
  };

  private start = (): void => {
    this.startInner().catch((error) =>
      this.setState({ signaling: false, error })
    );
  };

  private stopInner = async (): Promise<void> => {
    const pc = this.pc;
    this.pc = undefined;
    this.setState({ playing: false }, () =>
      Streamlit.setComponentValue({ playing: false })
    );

    if (pc == null) {
      return Promise.resolve();
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
    this.setState({ stopping: true });
    this.stopInner().finally(() => {
      this.setState({
        stopping: false,
        stream: null,
      });
    });
  };

  public componentDidUpdate() {
    if (this.pc == null) {
      return;
    }
    const pc = this.pc;
    if (pc.remoteDescription == null) {
      const sdpAnswerJson = this.props.args["sdp_answer_json"];
      if (sdpAnswerJson) {
        this.processAnswer(pc, sdpAnswerJson);
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
    const buttonDisabled =
      this.props.disabled || this.state.signaling || this.state.stopping;
    const mode = this.props.args["mode"];
    const { useVideo, useAudio } = getVideoAudioUsage(this.props.args);
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
              receivable && <Placeholder loading={this.state.signaling} />
            )}
          </Box>
          <Box display="flex" justifyContent="space-between">
            {this.state.playing ? (
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
                useVideo={useVideo}
                useAudio={useAudio}
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
