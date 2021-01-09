import {
  Streamlit,
  StreamlitComponentBase,
  withStreamlitConnection,
  ComponentProps,
} from "streamlit-component-lib";
import React, { ReactNode } from "react";
import Box from "@material-ui/core/Box";
import Button from "@material-ui/core/Button";

type WebRtcMode = "RECVONLY" | "SENDONLY" | "SENDRECV";
const isWebRtcMode = (val: unknown): val is WebRtcMode =>
  val === "RECVONLY" || val === "SENDONLY" || val === "SENDRECV";

const setupOffer = (
  pc: RTCPeerConnection,
  mode: WebRtcMode
): Promise<RTCSessionDescription | null> => {
  if (mode === "RECVONLY") {
    pc.addTransceiver("video", { direction: "recvonly" });
    pc.addTransceiver("audio", { direction: "recvonly" });
  }

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
  hasVideo: boolean;
  hasAudio: boolean;
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
      hasVideo: false,
      hasAudio: false,
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

    this.setState({ signaling: true, hasVideo: false, hasAudio: false });

    const config: RTCConfiguration =
      this.props.args.settings?.rtc_configuration || {};
    console.log("RTCConfiguration:", config);
    const pc = new RTCPeerConnection(config);

    // connect audio / video
    pc.addEventListener("track", (evt) => {
      if (evt.track.kind === "video") {
        const videoElem = this.videoRef.current;
        if (videoElem == null) {
          console.error("video element is not mounted");
          return;
        }

        videoElem.srcObject = evt.streams[0];
        this.setState({ hasVideo: true });
      } else {
        const audioElem = this.audioRef.current;
        if (audioElem == null) {
          console.error("audio element is not mounted");
          return;
        }

        audioElem.srcObject = evt.streams[0];
        this.setState({ hasAudio: true });
      }
    });

    if (mode === "SENDRECV" || mode === "SENDONLY") {
      const defaultConstraints = {
        audio: true,
        video: true,
      };
      const constraints: MediaStreamConstraints =
        this.props.args.settings?.media_stream_constraints ||
        defaultConstraints;
      console.log("MediaStreamConstraints:", constraints);

      if (constraints.audio || constraints.video) {
        const stream = await navigator.mediaDevices.getUserMedia(constraints);
        stream.getTracks().forEach((track) => {
          pc.addTrack(track, stream);
        });
      }
    }

    this.setState({ playing: true });

    setupOffer(pc, mode).then((offer) => {
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
    this.startInner().catch(() => this.setState({ signaling: false }));
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
      this.setState({ stopping: false, hasVideo: false, hasAudio: false });
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

  public render = (): ReactNode => {
    const buttonDisabled =
      this.props.disabled || this.state.signaling || this.state.stopping;

    return (
      <Box>
        <Box>
          <video
            style={{
              width: "100%",
            }}
            ref={this.videoRef}
            autoPlay
            controls
            onCanPlay={() => Streamlit.setFrameHeight()}
          />
        </Box>
        <Box>
          <audio ref={this.audioRef} autoPlay controls />
        </Box>
        <Box>
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
        </Box>
      </Box>
    );
  };
}

// "withStreamlitConnection" is a wrapper function. It bootstraps the
// connection between your component and the Streamlit app, and handles
// passing arguments from Python -> Component.
//
// You don't need to edit withStreamlitConnection (but you're welcome to!).
export default withStreamlitConnection(WebRtcStreamer);
