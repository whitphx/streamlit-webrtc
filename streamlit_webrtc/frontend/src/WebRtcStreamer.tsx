import React, { useState, useCallback } from "react";
import Box from "@mui/material/Box";
import Alert from "@mui/material/Alert";
import DeviceSelectForm, {
  DeviceSelectFormProps,
} from "./DeviceSelect/DeviceSelectForm";
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
import { getMediaUsage } from "./media-constraint";
import { ComponentValue, setComponentValue } from "./component-value";
import TranslatedButton from "./translation/components/TranslatedButton";
import "webrtc-adapter";

interface WebRtcStreamerInnerProps {
  disabled: boolean;
  mode: WebRtcMode;
  desiredPlayingState: boolean | undefined;
  sdpAnswerJson: string | undefined;
  rtcConfiguration: RTCConfiguration | undefined;
  mediaStreamConstraints: MediaStreamConstraints | undefined;
  videoHtmlAttrs: any;
  audioHtmlAttrs: any;
  onComponentValueChange: (newComponentValue: ComponentValue) => void;
}
const WebRtcStreamerInner: React.VFC<WebRtcStreamerInnerProps> = (props) => {
  const [deviceIds, setDeviceIds] = useState<{
    video: MediaDeviceInfo["deviceId"] | undefined;
    audio: MediaDeviceInfo["deviceId"] | undefined;
  }>({ video: undefined, audio: undefined });
  const { state, start, stop } = useWebRtc(
    props,
    deviceIds.video,
    deviceIds.audio,
    props.onComponentValueChange,
    useCallback(
      (openedDeviceIds) =>
        setDeviceIds({
          video: openedDeviceIds.video,
          audio: openedDeviceIds.audio,
        }),
      []
    )
  );

  const mode = props.mode;
  const buttonDisabled =
    props.disabled ||
    (state.webRtcState === "SIGNALLING" && !state.signallingTimedOut) || // Users can click the stop button after signalling timed out.
    state.webRtcState === "STOPPING" ||
    props.desiredPlayingState != null;
  const receivable = isWebRtcMode(mode) && isReceivable(mode);
  const transmittable = isWebRtcMode(mode) && isTransmittable(mode);
  const { videoEnabled, audioEnabled } = getMediaUsage(
    props.mediaStreamConstraints
  );

  const handleDeviceSelect = useCallback<DeviceSelectFormProps["onSelect"]>(
    ({ video, audio }) => {
      // TODO: Fix <DeviceSelectForm /> to return deviceId string instead of MediaDeviceInfo so that we can pass setDeviceIds to its callback directly removing this wrapper callback.
      setDeviceIds({ video: video?.deviceId, audio: audio?.deviceId });
    },
    []
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
        defaultVideoDeviceId={deviceIds.video ? deviceIds.video : null}
        defaultAudioDeviceId={deviceIds.audio ? deviceIds.audio : null}
        onSelect={handleDeviceSelect}
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
            variant="contained"
            onClick={stop}
            disabled={buttonDisabled}
            translationKey="stop"
            defaultText="Stop"
          />
        ) : (
          <TranslatedButton
            variant="contained"
            color="primary"
            onClick={start}
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
};

const WebRtcStreamer: React.VFC = () => {
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
};

export default WebRtcStreamer;
