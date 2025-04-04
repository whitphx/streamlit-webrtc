import { useState, useCallback } from "react";
import Box from "@mui/material/Box";
import Alert from "@mui/material/Alert";
import DeviceSelectForm from "./DeviceSelect/DeviceSelectForm";
import MediaStreamPlayer from "./MediaStreamPlayer";
import Placeholder from "./Placeholder";
import { useRenderData } from "streamlit-component-lib-react-hooks";
import {
  useWebRtc,
  WebRtcMode,
  isWebRtcMode,
  isReceivable,
  isTransmittable,
} from "./webrtc";
import { useTimer } from "./use-timeout";
import { getMediaUsage } from "./media-constraint";
import { ComponentValue, setComponentValue } from "./component-value";
import TranslatedButton from "./translation/components/TranslatedButton";
import "webrtc-adapter";

const BACKEND_VANILLA_ICE_TIMEOUT =
  5 * 1000 + // `aiortc` runs ICE in the Vanilla manner and its timeout is set to 5 seconds: https://github.com/aiortc/aioice/blob/fc863fde4676e1f67dce981b7f9592ab02c6a09a/src/aioice/ice.py#L881
  300; // ad-hoc delay to account for network latency and the time it takes to start the stream

interface WebRtcStreamerInnerProps {
  disabled: boolean;
  mode: WebRtcMode;
  desiredPlayingState: boolean | undefined;
  sdpAnswerJson: string | undefined;
  rtcConfiguration: RTCConfiguration | undefined;
  mediaStreamConstraints: MediaStreamConstraints | undefined;
  videoHtmlAttrs: Record<string, string>;
  audioHtmlAttrs: Record<string, string>;
  onComponentValueChange: (newComponentValue: ComponentValue) => void;
}
function WebRtcStreamerInner(props: WebRtcStreamerInnerProps) {
  const [deviceIds, setDeviceIds] = useState<{
    video?: MediaDeviceInfo["deviceId"] | undefined;
    audio?: MediaDeviceInfo["deviceId"] | undefined;
  }>({ video: undefined, audio: undefined });
  const { state, start, stop } = useWebRtc(
    props,
    deviceIds.video,
    deviceIds.audio,
    props.onComponentValueChange,
    setDeviceIds,
  );

  const {
    start: startTakingTooLongTimeout,
    clear: clearTakingTooLongTimeout,
    isTimedOut: isTakingTooLong,
  } = useTimer();
  const startWithNotification = useCallback(() => {
    clearTakingTooLongTimeout();
    start().then(() => {
      startTakingTooLongTimeout(BACKEND_VANILLA_ICE_TIMEOUT);
    });
  }, [start, startTakingTooLongTimeout, clearTakingTooLongTimeout]);

  const stopWithNotification = useCallback(() => {
    clearTakingTooLongTimeout();
    stop();
  }, [stop, clearTakingTooLongTimeout]);

  const mode = props.mode;
  const buttonDisabled =
    props.disabled ||
    state.webRtcState === "STOPPING" ||
    props.desiredPlayingState != null;
  const receivable = isWebRtcMode(mode) && isReceivable(mode);
  const transmittable = isWebRtcMode(mode) && isTransmittable(mode);
  const { videoEnabled, audioEnabled } = getMediaUsage(
    props.mediaStreamConstraints,
  );

  const [deviceSelectOpen, setDeviceSelectOpen] = useState(false);
  const openDeviceSelect = useCallback(() => {
    setDeviceSelectOpen(true);
  }, []);
  const closeDeviceSelect = useCallback(() => {
    setDeviceSelectOpen(false);
  }, []);
  if (deviceSelectOpen) {
    return (
      <DeviceSelectForm
        video={videoEnabled}
        audio={audioEnabled}
        defaultVideoDeviceId={deviceIds.video}
        defaultAudioDeviceId={deviceIds.audio}
        onSelect={setDeviceIds}
        onClose={closeDeviceSelect}
      />
    );
  }

  return (
    <Box>
      {state.error && (
        <Alert severity="error">
          {state.error.name}: {state.error.message}
        </Alert>
      )}
      <Box py={1} display="flex">
        {state.stream ? (
          <MediaStreamPlayer
            stream={state.stream}
            userDefinedVideoAttrs={props.videoHtmlAttrs}
            userDefinedAudioAttrs={props.audioHtmlAttrs}
          />
        ) : (
          receivable && (
            <Placeholder loading={state.webRtcState === "SIGNALLING"} />
          )
        )}
      </Box>
      <Box display="flex" justifyContent="space-between">
        {state.webRtcState === "PLAYING" ||
        state.webRtcState === "SIGNALLING" ? (
          <TranslatedButton
            variant={
              state.webRtcState === "SIGNALLING" && !isTakingTooLong
                ? "outlined"
                : "contained"
            }
            onClick={stopWithNotification}
            disabled={buttonDisabled}
            translationKey="stop"
            defaultText="Stop"
          />
        ) : (
          <TranslatedButton
            variant="contained"
            color="primary"
            onClick={startWithNotification}
            disabled={buttonDisabled}
            translationKey="start"
            defaultText="Start"
          />
        )}
        {transmittable && state.webRtcState === "STOPPED" && (
          <TranslatedButton
            color="inherit"
            onClick={openDeviceSelect}
            translationKey="select_device"
            defaultText="Select Device"
          />
        )}
      </Box>
    </Box>
  );
}

function WebRtcStreamer() {
  const renderData = useRenderData();

  const mode = renderData.args["mode"];
  const desiredPlayingState = renderData.args["desired_playing_state"];
  const sdpAnswerJson = renderData.args["sdp_answer_json"];
  const rtcConfiguration: RTCConfiguration = renderData.args.rtc_configuration;
  const mediaStreamConstraints: MediaStreamConstraints =
    renderData.args.media_stream_constraints;
  const videoHtmlAttrs = renderData.args.video_html_attrs;
  const audioHtmlAttrs = renderData.args.audio_html_attrs;

  if (!isWebRtcMode(mode)) {
    throw new Error(`Invalid mode ${mode}`);
  }

  return (
    <WebRtcStreamerInner
      disabled={renderData.disabled}
      mode={mode}
      desiredPlayingState={desiredPlayingState}
      sdpAnswerJson={sdpAnswerJson}
      rtcConfiguration={rtcConfiguration}
      mediaStreamConstraints={mediaStreamConstraints}
      videoHtmlAttrs={videoHtmlAttrs}
      audioHtmlAttrs={audioHtmlAttrs}
      onComponentValueChange={setComponentValue}
    />
  );
}

export default WebRtcStreamer;
