import {
  Streamlit,
  StreamlitComponentBase,
  withStreamlitConnection,
  ComponentProps,
} from "streamlit-component-lib"
import React, { ReactNode } from "react"

interface State {
  playing: boolean
}

class MyComponent extends StreamlitComponentBase<State> {
  private pc: RTCPeerConnection | undefined
  private videoRef: React.RefObject<HTMLVideoElement>
  private audioRef: React.RefObject<HTMLAudioElement>

  constructor(props: ComponentProps) {
    super(props)
    this.videoRef = React.createRef()
    this.audioRef = React.createRef()

    this.state = {
      playing: false,
    }
  }

  private sendOffer = (pc: RTCPeerConnection): Promise<void> => {
    pc.addTransceiver("video", { direction: "recvonly" })
    pc.addTransceiver("audio", { direction: "recvonly" })

    return pc
      .createOffer()
      .then(offer => {
        console.log("Created offer:", offer)
        return pc.setLocalDescription(offer)
      })
      .then(() => {
        console.log("Wait for ICE gethering...")
        // Wait for ICE gathering to complete
        return new Promise<void>(resolve => {
          if (pc.iceGatheringState === "complete") {
            resolve()
          } else {
            const checkState = () => {
              if (pc.iceGatheringState === "complete") {
                pc.removeEventListener("icegatheringstatechange", checkState)
                resolve()
              }
            }
            pc.addEventListener("icegatheringstatechange", checkState)
          }
        })
      })
      .then(() => {
        const offer = pc.localDescription
        if (offer) {
          console.log("Send sdpOffer", offer.toJSON())
          Streamlit.setComponentValue({
            sdpOffer: offer.toJSON(),
            playing: true,
          })
        } else {
          console.error("Offer has not been created")
        }
      })
  }

  private processAnswer = (
    pc: RTCPeerConnection,
    sdpAnswerJson: string
  ): Promise<void> => {
    const sdpAnswer = JSON.parse(sdpAnswerJson)
    console.log("Receive answer sdpOffer", sdpAnswer)
    return pc.setRemoteDescription(sdpAnswer)
  }

  private start = () => {
    const config: RTCConfiguration = {
      // TODO
      iceServers: [{ urls: ["stun:stun.l.google.com:19302"] }],
    }
    const pc = new RTCPeerConnection(config)

    // connect audio / video
    pc.addEventListener("track", evt => {
      if (evt.track.kind === "video") {
        const videoElem = this.videoRef.current
        if (videoElem == null) {
          console.error("video element is not mounted")
          return
        }

        videoElem.srcObject = evt.streams[0]
      } else {
        const audioElem = this.audioRef.current
        if (audioElem == null) {
          console.error("audio element is not mounted")
          return
        }

        audioElem.srcObject = evt.streams[0]
      }
    })

    this.setState({ playing: true })

    this.sendOffer(pc)
    this.pc = pc
  }

  private stop = () => {
    const pc = this.pc
    this.pc = undefined
    this.setState({ playing: false }, () =>
      Streamlit.setComponentValue({ playing: false })
    )

    // close peer connection
    setTimeout(() => {
      pc?.close()
    }, 500)
  }

  public componentDidUpdate() {
    if (this.pc == null) {
      return
    }
    const pc = this.pc
    if (pc.remoteDescription == null) {
      const sdpAnswerJson = this.props.args["sdp_answer_json"]
      if (sdpAnswerJson) {
        this.processAnswer(pc, sdpAnswerJson).then(() => {
          console.log("Remote description is set")
        })
      }
    }
  }

  public render = (): ReactNode => {
    return (
      <div>
        <video
          ref={this.videoRef}
          autoPlay
          controls
          style={{ width: "100%" }}
          onCanPlay={() => Streamlit.setFrameHeight()}
        />
        <audio ref={this.audioRef} autoPlay controls />
        {this.state.playing ? (
          <button onClick={this.stop}>Stop</button>
        ) : (
          <button onClick={this.start}>Start</button>
        )}
      </div>
    )
  }
}

// "withStreamlitConnection" is a wrapper function. It bootstraps the
// connection between your component and the Streamlit app, and handles
// passing arguments from Python -> Component.
//
// You don't need to edit withStreamlitConnection (but you're welcome to!).
export default withStreamlitConnection(MyComponent)
