import { Streamlit } from "streamlit-component-lib";
import React, {
  useReducer,
  Reducer,
  useCallback,
  useState,
  useEffect,
} from "react";
import NativeSelect, { NativeSelectProps } from "@mui/material/NativeSelect";
import Alert from "@mui/material/Alert";
import Stack from "@mui/material/Stack";
import InputLabel from "@mui/material/InputLabel";
import FormControl from "@mui/material/FormControl";
import DeviceSelectContainer from "./components/DeviceSelectContainer";
import VideoPreviewContainer from "./components/VideoPreviewContainer";
import DeviceSelectMessage from "./components/DeviceSelectMessage";
import VoidVideoPreview from "./components/VoidVideoPreview";
import Defer from "./components/Defer";
import VideoPreview from "./VideoPreview";

function stopAllTracks(stream: MediaStream) {
  stream.getVideoTracks().forEach((track) => track.stop());
  stream.getAudioTracks().forEach((track) => track.stop());
}

function ensureValidSelection(
  devices: MediaDeviceInfo[],
  selectedDeviceId: MediaDeviceInfo["deviceId"] | null
): MediaDeviceInfo["deviceId"] | null {
  const deviceIds = devices.map((d) => d.deviceId);
  if (selectedDeviceId && deviceIds.includes(selectedDeviceId)) {
    return selectedDeviceId;
  }
  if (deviceIds.length === 0) {
    return null;
  }
  return deviceIds[0];
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

export interface DeviceSelectProps {
  video: boolean;
  audio: boolean;
  onSelect: (devices: {
    video: MediaDeviceInfo | null;
    audio: MediaDeviceInfo | null;
  }) => void;
}
const DeviceSelect: React.VFC<DeviceSelectProps> = (props) => {
  const { video: useVideo, audio: useAudio, onSelect } = props;

  const [waitingForPermission, setWaitingForPermission] = useState(false);
  const [error, setError] = useState<Error>();
  const [permitted, setPermitted] = useState(false);

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
    selectedVideoInputDeviceId: null,
    selectedAudioInputDeviceId: null,
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

  // Call `getUserMedia()` to ask the user for the permission.
  useEffect(() => {
    if (typeof navigator?.mediaDevices?.getUserMedia !== "function") {
      deviceSelectionDispatch({ type: "SET_UNAVAILABLE" });
      return;
    }

    setPermitted(false);
    setError(undefined);
    setWaitingForPermission(true);
    navigator.mediaDevices
      .getUserMedia({ video: useVideo, audio: useAudio })
      .then((stream) => {
        stopAllTracks(stream);

        setPermitted(true);
      })
      .catch((err) => {
        setError(err);
      })
      .finally(() => setWaitingForPermission(false));
  }, [useVideo, useAudio, updateDeviceList]);

  // After permitted, update the device list.
  useEffect(() => {
    if (!permitted) {
      return;
    }

    // The first update just after the permission granted
    updateDeviceList();

    // Event-based updates
    const handleDeviceChange = () => updateDeviceList();
    navigator.mediaDevices.ondevicechange = handleDeviceChange;

    // Clean up the event handler
    return () => {
      if (navigator.mediaDevices.ondevicechange === handleDeviceChange) {
        navigator.mediaDevices.ondevicechange = null;
      }
    };
  }, [permitted, updateDeviceList]);

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
    onSelect({ video: videoInput || null, audio: audioInput || null });
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
    Streamlit.setFrameHeight();
  });

  if (unavailable) {
    return <DeviceSelectMessage>Unavailable</DeviceSelectMessage>;
  }

  if (waitingForPermission) {
    return (
      <Defer time={1000}>
        <DeviceSelectMessage>
          Please allow the app to access the media devices
        </DeviceSelectMessage>
      </Defer>
    );
  }

  if (error) {
    if (error instanceof DOMException && error.name === "NotReadableError") {
      return (
        <DeviceSelectMessage>
          Device not available ({error.message})
        </DeviceSelectMessage>
      );
    } else if (
      error instanceof DOMException &&
      error.name === "NotAllowedError"
    ) {
      return (
        <DeviceSelectMessage>
          Access denied ({error.message})
        </DeviceSelectMessage>
      );
    } else {
      return (
        <DeviceSelectMessage>
          <Alert severity="error">
            {error.name}: {error.message}
          </Alert>
        </DeviceSelectMessage>
      );
    }
  }

  if (!permitted) {
    // Usually this block is not reached because this case should be handled
    // by the "NotAllowedError" block in the previous if-clause.
    return <DeviceSelectMessage>Access denied</DeviceSelectMessage>;
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
