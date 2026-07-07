import {
  lazy,
  Suspense,
  useState,
  useCallback,
  useEffect,
  useRef,
} from "react";
import Box from "@mui/material/Box";
import InputMediaControls from "./InputMediaControls";
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
import { loadPersistedDeviceIds, persistDeviceIds } from "./device-storage";
import TranslatedButton from "./translation/components/TranslatedButton";
import InfoHeader from "./InfoHeader";

const DeviceSelectForm = lazy(() => import("./DeviceSelect/DeviceSelectForm"));

// How long a connection attempt may take before the "taking too long" hint
// is shown. Signalling is trickle-ICE based and normally fast, but candidate
// gathering and connectivity checks can still take a while on slow networks.
const CONNECTION_ATTEMPT_TIMEOUT = 10 * 1000;

interface WebRtcStreamerInnerProps {
  disabled: boolean;
  mode: WebRtcMode;
  componentKey: string | undefined;
  desiredPlayingState: boolean | undefined;
  sdpAnswerJson: string | undefined;
  answererIceCandidatesJson: string | undefined;
  rtcConfiguration: RTCConfiguration | undefined;
  mediaStreamConstraints: MediaStreamConstraints | undefined;
  sendbackVideo: boolean;
  sendbackAudio: boolean;
  videoHtmlAttrs: Record<string, string>;
  audioHtmlAttrs: Record<string, string>;
  mediaToggleControls: boolean;
  onComponentValueChange: (newComponentValue: ComponentValue) => void;
}
export function WebRtcStreamerInner(props: WebRtcStreamerInnerProps) {
  const { componentKey } = props;
  const [deviceIds, setDeviceIds] = useState<{
    video?: MediaDeviceInfo["deviceId"] | undefined;
    audio?: MediaDeviceInfo["deviceId"] | undefined;
  }>(() => loadPersistedDeviceIds(componentKey));

  // Persist whenever the selection changes — both the DeviceSelect form's
  // `onSelect` and the WebRTC hook's `onDevicesOpened` route through
  // `setDeviceIds`, so this single effect covers both paths.
  const initialDeviceIdsRef = useRef(deviceIds);
  useEffect(() => {
    if (deviceIds === initialDeviceIdsRef.current) return;
    persistDeviceIds(componentKey, deviceIds);
  }, [componentKey, deviceIds]);
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
      startTakingTooLongTimeout(CONNECTION_ATTEMPT_TIMEOUT);
    });
  }, [start, startTakingTooLongTimeout, clearTakingTooLongTimeout]);

  const stopWithNotification = useCallback(() => {
    clearTakingTooLongTimeout();
    stop();
  }, [stop, clearTakingTooLongTimeout]);

  const mode = props.mode;
  const userControlsPlayingState = props.desiredPlayingState == null;
  const buttonDisabled = props.disabled || state.webRtcState === "STOPPING";
  const receivable = isWebRtcMode(mode) && isReceivable(mode);
  const transmittable = isWebRtcMode(mode) && isTransmittable(mode);
  const inputMediaStream = state.inputMediaStream;
  const showMediaToggleControls =
    props.mediaToggleControls &&
    transmittable &&
    inputMediaStream != null &&
    (state.webRtcState === "SIGNALLING" || state.webRtcState === "PLAYING");
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
      <Suspense fallback={null}>
        <DeviceSelectForm
          video={videoEnabled}
          audio={audioEnabled}
          defaultVideoDeviceId={deviceIds.video}
          defaultAudioDeviceId={deviceIds.audio}
          onSelect={setDeviceIds}
          onClose={closeDeviceSelect}
        />
      </Suspense>
    );
  }

  return (
    <Box>
      <InfoHeader
        error={state.error}
        shouldShowTakingTooLongWarning={
          state.webRtcState === "SIGNALLING" && isTakingTooLong
        }
      />
      <Box py={1} display="flex">
        {state.outputMediaStream ? (
          <MediaStreamPlayer
            stream={state.outputMediaStream}
            userDefinedVideoAttrs={props.videoHtmlAttrs}
            userDefinedAudioAttrs={props.audioHtmlAttrs}
          />
        ) : (
          receivable && (
            <Placeholder loading={state.webRtcState === "SIGNALLING"} />
          )
        )}
      </Box>
      {(userControlsPlayingState || showMediaToggleControls) && (
        <Box display="flex" alignItems="center" justifyContent="space-between">
          <Box display="flex" alignItems="center" gap={1}>
            {userControlsPlayingState && (
              <>
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
              </>
            )}
            {showMediaToggleControls && inputMediaStream != null && (
              <InputMediaControls
                disabled={buttonDisabled}
                stream={inputMediaStream}
              />
            )}
          </Box>
          {userControlsPlayingState &&
            transmittable &&
            state.webRtcState === "STOPPED" && (
              <TranslatedButton
                color="inherit"
                onClick={openDeviceSelect}
                translationKey="select_device"
                defaultText="Select Device"
              />
            )}
        </Box>
      )}
    </Box>
  );
}

function WebRtcStreamer() {
  const renderData = useRenderData();

  const mode = renderData.args["mode"];
  const componentKey: string | undefined = renderData.args["component_key"];
  const desiredPlayingState = renderData.args["desired_playing_state"];
  const sdpAnswerJson = renderData.args["sdp_answer_json"];
  const answererIceCandidatesJson =
    renderData.args["answerer_ice_candidates_json"];
  const rtcConfiguration: RTCConfiguration = renderData.args.rtc_configuration;
  const mediaStreamConstraints: MediaStreamConstraints =
    renderData.args.media_stream_constraints;
  const sendbackVideo: boolean = renderData.args.sendback_video ?? true;
  const sendbackAudio: boolean = renderData.args.sendback_audio ?? true;
  const videoHtmlAttrs = renderData.args.video_html_attrs;
  const audioHtmlAttrs = renderData.args.audio_html_attrs;
  const mediaToggleControls: boolean =
    renderData.args.media_toggle_controls ?? true;

  if (!isWebRtcMode(mode)) {
    throw new Error(`Invalid mode ${mode}`);
  }

  return (
    <WebRtcStreamerInner
      disabled={renderData.disabled}
      mode={mode}
      componentKey={componentKey}
      desiredPlayingState={desiredPlayingState}
      sdpAnswerJson={sdpAnswerJson}
      answererIceCandidatesJson={answererIceCandidatesJson}
      rtcConfiguration={rtcConfiguration}
      mediaStreamConstraints={mediaStreamConstraints}
      sendbackVideo={sendbackVideo}
      sendbackAudio={sendbackAudio}
      videoHtmlAttrs={videoHtmlAttrs}
      audioHtmlAttrs={audioHtmlAttrs}
      mediaToggleControls={mediaToggleControls}
      onComponentValueChange={setComponentValue}
    />
  );
}

export default WebRtcStreamer;
