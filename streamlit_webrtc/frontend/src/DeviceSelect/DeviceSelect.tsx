import { Streamlit } from "streamlit-component-lib";
import { useCallback, useState, useEffect, useRef } from "react";
import NativeSelect from "@mui/material/NativeSelect";
import Alert from "@mui/material/Alert";
import Stack from "@mui/material/Stack";
import InputLabel from "@mui/material/InputLabel";
import FormControl from "@mui/material/FormControl";
import DeviceSelectContainer from "./components/DeviceSelectContainer";
import VideoPreviewContainer from "./components/VideoPreviewContainer";
import Message from "./components/messages/Message";
import MediaApiNotAvailableMessage from "./components/messages/MediaApiNotAvailableMessage";
import AskPermissionMessage from "./components/messages/AskPermissionMessage";
import AccessDeniedMessage from "./components/messages/AccessDeniedMessage";
import DeviceNotAvailableMessage from "./components/messages/DeviceNotAvailableMessage";
import VoidVideoPreview from "./components/VoidVideoPreview";
import Defer from "./components/Defer";
import VideoPreview from "./VideoPreview";
import { stopAllTracks } from "./utils";
import { useMediaInputDevices } from "../use-media-input-devices";
import type { InputDeviceKind } from "../webrtc";

function ensureValidSelection(
  devices: MediaDeviceInfo[],
  selectedDeviceId: MediaDeviceInfo["deviceId"] | undefined,
): MediaDeviceInfo["deviceId"] | undefined {
  const deviceIds = devices.map((d) => d.deviceId);
  if (selectedDeviceId && deviceIds.includes(selectedDeviceId)) {
    return selectedDeviceId;
  }
  if (deviceIds.length > 0) {
    return deviceIds[0];
  }
  return undefined;
}

// `MEDIA_API_UNAVAILABLE` covers the half of the media API this component needs
// that the device list does not: a browser exposing `enumerateDevices` but no
// `getUserMedia` leaves nothing to wait for, and there is no permission to ask.
type PermissionState = "WAITING" | "ALLOWED" | "MEDIA_API_UNAVAILABLE" | Error;

export interface DeviceSelectProps {
  video: boolean;
  audio: boolean;
  defaultVideoDeviceId: MediaDeviceInfo["deviceId"] | undefined;
  defaultAudioDeviceId: MediaDeviceInfo["deviceId"] | undefined;
  onSelectionResolved: (devices: {
    video?: MediaDeviceInfo["deviceId"];
    audio?: MediaDeviceInfo["deviceId"];
  }) => void;
  onVideoSelect: (
    deviceId: MediaDeviceInfo["deviceId"],
  ) => Promise<void> | void;
  onAudioSelect: (
    deviceId: MediaDeviceInfo["deviceId"],
  ) => Promise<void> | void;
}
function DeviceSelect(props: DeviceSelectProps) {
  const {
    video: useVideo,
    audio: useAudio,
    defaultVideoDeviceId,
    defaultAudioDeviceId,
    onSelectionResolved,
    onVideoSelect,
    onAudioSelect,
  } = props;

  const [permissionState, setPermissionState] =
    useState<PermissionState>("WAITING");

  const {
    devices: { video: videoInputs, audio: audioInputs },
    unavailable,
    refresh: refreshDeviceList,
  } = useMediaInputDevices();

  const [requestedDeviceIds, setRequestedDeviceIds] = useState<
    Partial<Record<InputDeviceKind, MediaDeviceInfo["deviceId"]>>
  >({
    video: defaultVideoDeviceId,
    audio: defaultAudioDeviceId,
  });
  const selectedVideoInputDeviceId = ensureValidSelection(
    videoInputs,
    requestedDeviceIds.video,
  );
  const selectedAudioInputDeviceId = ensureValidSelection(
    audioInputs,
    requestedDeviceIds.audio,
  );

  // These values are passed to inside the useEffect below via a ref
  // because they are used there only for UX improvement
  // and should not be added to the dependency list to avoid triggering re-execution.
  const defaultDeviceIdsRef = useRef({
    video: defaultVideoDeviceId,
    audio: defaultAudioDeviceId,
  });
  defaultDeviceIdsRef.current = {
    video: defaultVideoDeviceId,
    audio: defaultAudioDeviceId,
  };
  const selectionRequestIdsRef = useRef({ video: 0, audio: 0 });
  // Call `getUserMedia()` to ask the user for the permission.
  useEffect(() => {
    if (typeof navigator?.mediaDevices?.getUserMedia !== "function") {
      setPermissionState("MEDIA_API_UNAVAILABLE");
      return;
    }

    setPermissionState("WAITING");

    const { video: videoDeviceId, audio: audioDeviceId } =
      defaultDeviceIdsRef.current;
    navigator.mediaDevices
      .getUserMedia({
        // Specify the target devices if the user already selected specific ones.
        // This is not mandatory but beneficial for better UX
        // as unused devices are not accessed so that their LED indicators
        // will not be unnecessarily turned on.
        video:
          useVideo && videoDeviceId ? { deviceId: videoDeviceId } : useVideo,
        audio:
          useAudio && audioDeviceId ? { deviceId: audioDeviceId } : useAudio,
      })
      .then(async (stream) => {
        stopAllTracks(stream);

        // Device labels are only populated once the permission is granted, so
        // the list this component renders comes from an enumeration made here
        // rather than the one on mount.
        await refreshDeviceList();

        setPermissionState("ALLOWED");
      })
      .catch((err) => {
        setPermissionState(err);
      });
  }, [useVideo, useAudio, refreshDeviceList]);

  const handleInputChange = useCallback(
    (kind: InputDeviceKind, deviceId: MediaDeviceInfo["deviceId"]) => {
      const requestId = ++selectionRequestIdsRef.current[kind];
      setRequestedDeviceIds((prev) => ({ ...prev, [kind]: deviceId }));
      const onSelect = kind === "video" ? onVideoSelect : onAudioSelect;
      void Promise.resolve()
        .then(() => onSelect(deviceId))
        .catch(() => {
          // Only the latest request may roll the selection back; an older one
          // failing after it would drop a choice the user has already made.
          if (selectionRequestIdsRef.current[kind] !== requestId) {
            return;
          }
          setRequestedDeviceIds((prev) => ({
            ...prev,
            [kind]: defaultDeviceIdsRef.current[kind],
          }));
        });
    },
    [onVideoSelect, onAudioSelect],
  );

  useEffect(() => {
    const videoInput = useVideo
      ? videoInputs.find((d) => d.deviceId === selectedVideoInputDeviceId)
      : null;
    const audioInput = useAudio
      ? audioInputs.find((d) => d.deviceId === selectedAudioInputDeviceId)
      : null;
    onSelectionResolved({
      video: videoInput?.deviceId,
      audio: audioInput?.deviceId,
    });
  }, [
    useVideo,
    useAudio,
    onSelectionResolved,
    videoInputs,
    audioInputs,
    selectedVideoInputDeviceId,
    selectedAudioInputDeviceId,
  ]);

  useEffect(() => {
    setTimeout(() => Streamlit.setFrameHeight());
  });

  if (unavailable || permissionState === "MEDIA_API_UNAVAILABLE") {
    return <MediaApiNotAvailableMessage />;
  }

  if (permissionState === "WAITING") {
    return (
      <Defer time={1000}>
        <AskPermissionMessage />
      </Defer>
    );
  }

  if (permissionState instanceof Error) {
    const error = permissionState;
    if (
      error instanceof DOMException &&
      (error.name === "NotReadableError" || error.name === "NotFoundError")
    ) {
      return <DeviceNotAvailableMessage error={error} />;
    } else if (
      error instanceof DOMException &&
      error.name === "NotAllowedError"
    ) {
      return <AccessDeniedMessage error={error} />;
    } else {
      return (
        <Message>
          <Alert severity="error">
            {error.name}: {error.message}
          </Alert>
        </Message>
      );
    }
  }

  return (
    <DeviceSelectContainer>
      <VideoPreviewContainer>
        {useVideo && selectedVideoInputDeviceId ? (
          <VideoPreview deviceId={selectedVideoInputDeviceId} />
        ) : (
          <VoidVideoPreview />
        )}
      </VideoPreviewContainer>
      <Stack spacing={2} justifyContent="center">
        {useVideo && selectedVideoInputDeviceId && (
          <FormControl fullWidth>
            <InputLabel htmlFor="device-select-video-input">
              Video Input
            </InputLabel>
            <NativeSelect
              inputProps={{
                name: "video-input",
                id: "device-select-video-input",
              }}
              value={selectedVideoInputDeviceId}
              onChange={(e) => handleInputChange("video", e.target.value)}
            >
              {videoInputs.map((device) => (
                <option key={device.deviceId} value={device.deviceId}>
                  {device.label}
                </option>
              ))}
            </NativeSelect>
          </FormControl>
        )}
        {useAudio && selectedAudioInputDeviceId && (
          <FormControl fullWidth>
            <InputLabel htmlFor="device-select-audio-input">
              Audio Input
            </InputLabel>
            <NativeSelect
              inputProps={{
                name: "audio-input",
                id: "device-select-audio-input",
              }}
              value={selectedAudioInputDeviceId}
              onChange={(e) => handleInputChange("audio", e.target.value)}
            >
              {audioInputs.map((device) => (
                <option key={device.deviceId} value={device.deviceId}>
                  {device.label}
                </option>
              ))}
            </NativeSelect>
          </FormControl>
        )}
      </Stack>
    </DeviceSelectContainer>
  );
}

export default DeviceSelect;
