import { Streamlit } from "streamlit-component-lib";
import React, {
  useReducer,
  Reducer,
  useCallback,
  useState,
  useEffect,
  useRef,
} from "react";
import NativeSelect, { NativeSelectProps } from "@mui/material/NativeSelect";
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

function ensureValidSelection(
  devices: MediaDeviceInfo[],
  selectedDeviceId: MediaDeviceInfo["deviceId"] | null
): MediaDeviceInfo["deviceId"] | null {
  const deviceIds = devices.map((d) => d.deviceId);
  if (selectedDeviceId && deviceIds.includes(selectedDeviceId)) {
    return selectedDeviceId;
  }
  if (deviceIds.length > 0) {
    return deviceIds[0];
  }
  return null;
}

interface DeviceSelectionState {
  unavailable: boolean;
  videoInputs: MediaDeviceInfo[];
  audioInputs: MediaDeviceInfo[];
  audioOutputs: MediaDeviceInfo[];
  // TODO: Add selectedAudioOutputDeviceId
  selectedVideoInputDeviceId: MediaDeviceInfo["deviceId"] | null;
  selectedAudioInputDeviceId: MediaDeviceInfo["deviceId"] | null;
}
interface DeviceSelectionActionBase {
  type: string;
}
interface DeviceSelectionSetUnavailableAction
  extends DeviceSelectionActionBase {
  type: "SET_UNAVAILABLE";
}
interface DeviceSelectionUpdateDevicesAction extends DeviceSelectionActionBase {
  type: "UPDATE_DEVICES";
  devices: MediaDeviceInfo[];
}
interface DeviceSelectionUpdateSelectedDeviceIdAction
  extends DeviceSelectionActionBase {
  type: "UPDATE_SELECTED_DEVICE_ID";
  payload: {
    selectedVideoInputDeviceId?: MediaDeviceInfo["deviceId"] | null;
    selectedAudioInputDeviceId?: MediaDeviceInfo["deviceId"] | null;
  };
}
type DeviceSelectionAction =
  | DeviceSelectionSetUnavailableAction
  | DeviceSelectionUpdateDevicesAction
  | DeviceSelectionUpdateSelectedDeviceIdAction;
const deviceSelectionReducer: Reducer<
  DeviceSelectionState,
  DeviceSelectionAction
> = (state, action) => {
  switch (action.type) {
    case "SET_UNAVAILABLE": {
      return {
        unavailable: true,
        videoInputs: [],
        audioInputs: [],
        audioOutputs: [],
        selectedVideoInputDeviceId: null,
        selectedAudioInputDeviceId: null,
      };
    }
    case "UPDATE_DEVICES": {
      const devices = action.devices;
      const videoInputs = devices.filter((d) => d.kind === "videoinput");
      const audioInputs = devices.filter((d) => d.kind === "audioinput");
      const audioOutputs = devices.filter((d) => d.kind === "audiooutput");

      const selectedVideoInputDeviceId = ensureValidSelection(
        videoInputs,
        state.selectedVideoInputDeviceId
      );
      const selectedAudioInputDeviceId = ensureValidSelection(
        audioInputs,
        state.selectedAudioInputDeviceId
      );

      return {
        ...state,
        videoInputs,
        audioInputs,
        audioOutputs,
        selectedVideoInputDeviceId,
        selectedAudioInputDeviceId,
      };
    }
    case "UPDATE_SELECTED_DEVICE_ID": {
      return {
        ...state,
        ...action.payload,
      };
    }
  }
};

type PermissionState = "WAITING" | "ALLOWED" | Error;

export interface DeviceSelectProps {
  video: boolean;
  audio: boolean;
  defaultVideoDeviceId: MediaDeviceInfo["deviceId"] | null;
  defaultAudioDeviceId: MediaDeviceInfo["deviceId"] | null;
  onSelect: (devices: {
    video: MediaDeviceInfo["deviceId"] | undefined;
    audio: MediaDeviceInfo["deviceId"] | undefined;
  }) => void;
}
const DeviceSelect: React.VFC<DeviceSelectProps> = (props) => {
  const {
    video: useVideo,
    audio: useAudio,
    defaultVideoDeviceId,
    defaultAudioDeviceId,
    onSelect,
  } = props;

  const [permissionState, setPermissionState] =
    useState<PermissionState>("WAITING");

  const [
    {
      unavailable,
      videoInputs,
      selectedVideoInputDeviceId,
      audioInputs,
      selectedAudioInputDeviceId,
    },
    deviceSelectionDispatch,
  ] = useReducer(deviceSelectionReducer, {
    unavailable: false,
    videoInputs: [],
    audioInputs: [],
    audioOutputs: [],
    selectedVideoInputDeviceId: defaultVideoDeviceId,
    selectedAudioInputDeviceId: defaultAudioDeviceId,
  });

  // Ref: https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/ondevicechange#example
  const updateDeviceList = useCallback(() => {
    if (typeof navigator?.mediaDevices?.enumerateDevices !== "function") {
      deviceSelectionDispatch({ type: "SET_UNAVAILABLE" });
      return;
    }

    return navigator.mediaDevices.enumerateDevices().then((devices) => {
      deviceSelectionDispatch({
        type: "UPDATE_DEVICES",
        devices,
      });
    });
  }, []);

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
  // Call `getUserMedia()` to ask the user for the permission.
  useEffect(() => {
    if (typeof navigator?.mediaDevices?.getUserMedia !== "function") {
      deviceSelectionDispatch({ type: "SET_UNAVAILABLE" });
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

        await updateDeviceList();

        setPermissionState("ALLOWED");
      })
      .catch((err) => {
        setPermissionState(err);
      });
  }, [useVideo, useAudio, updateDeviceList]);

  // Set up the ondevicechange event handler
  useEffect(() => {
    const handleDeviceChange = () => updateDeviceList();
    navigator.mediaDevices.ondevicechange = handleDeviceChange;

    return () => {
      if (navigator.mediaDevices.ondevicechange === handleDeviceChange) {
        navigator.mediaDevices.ondevicechange = null;
      }
    };
  }, [updateDeviceList]);

  const handleVideoInputChange = useCallback<
    NonNullable<NativeSelectProps["onChange"]>
  >((e) => {
    deviceSelectionDispatch({
      type: "UPDATE_SELECTED_DEVICE_ID",
      payload: {
        selectedVideoInputDeviceId: e.target.value,
      },
    });
  }, []);

  const handleAudioInputChange = useCallback<
    NonNullable<NativeSelectProps["onChange"]>
  >((e) => {
    deviceSelectionDispatch({
      type: "UPDATE_SELECTED_DEVICE_ID",
      payload: {
        selectedAudioInputDeviceId: e.target.value,
      },
    });
  }, []);

  // Call onSelect
  useEffect(() => {
    const videoInput = useVideo
      ? videoInputs.find((d) => d.deviceId === selectedVideoInputDeviceId)
      : null;
    const audioInput = useAudio
      ? audioInputs.find((d) => d.deviceId === selectedAudioInputDeviceId)
      : null;
    onSelect({ video: videoInput?.deviceId, audio: audioInput?.deviceId });
  }, [
    useVideo,
    useAudio,
    onSelect,
    videoInputs,
    audioInputs,
    selectedVideoInputDeviceId,
    selectedAudioInputDeviceId,
  ]);

  useEffect(() => {
    setTimeout(() => Streamlit.setFrameHeight());
  });

  if (unavailable) {
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
              onChange={handleVideoInputChange}
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
              onChange={handleAudioInputChange}
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
};

export default DeviceSelect;
