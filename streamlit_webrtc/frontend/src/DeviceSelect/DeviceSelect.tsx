import React, {
  useReducer,
  Reducer,
  useCallback,
  useState,
  useEffect,
} from "react";
import Select, { SelectProps } from "@mui/material/Select";
import MenuItem from "@mui/material/MenuItem";
import VideoPreview from "./VideoPreview";

function stopAllTracks(stream: MediaStream) {
  stream.getVideoTracks().forEach((track) => track.stop());
  stream.getAudioTracks().forEach((track) => track.stop());
}

function ensureValidSelection(
  devices: MediaDeviceInfo[],
  selectedDeviceId: MediaDeviceInfo["deviceId"]
): MediaDeviceInfo["deviceId"] | null {
  const deviceIds = devices.map((d) => d.deviceId);
  if (deviceIds.includes(selectedDeviceId)) {
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
    selectedVideoInputDeviceId?: MediaDeviceInfo["deviceId"];
    selectedAudioInputDeviceId?: MediaDeviceInfo["deviceId"];
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
  const [waitingForPermission, setWaitingForPermission] = useState(false);
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
    setWaitingForPermission(true);
    navigator.mediaDevices
      .getUserMedia({ video: props.video, audio: props.audio })
      .then((stream) => {
        stopAllTracks(stream);

        setPermitted(true);
      })
      .finally(() => setWaitingForPermission(false));
  }, [props.video, props.audio, updateDeviceList]);

  // After permitted, update the device list.
  useEffect(() => {
    if (!permitted) {
      return;
    }

    // The first update just after the permission granted
    updateDeviceList();

    // Event-based updates
    navigator.mediaDevices.ondevicechange = function (event) {
      updateDeviceList();
    };

    // Clean up the event handler
    return () => {
      navigator.mediaDevices.ondevicechange = undefined;
    };
  }, [permitted, updateDeviceList]);

  const handleVideoInputChange = useCallback<
    SelectProps<typeof selectedVideoInputDeviceId>["onChange"]
  >((e) => {
    deviceSelectionDispatch({
      type: "UPDATE_SELECTED_DEVICE_ID",
      payload: {
        selectedVideoInputDeviceId: e.target.value,
      },
    });
  }, []);

  const handleAudioInputChange = useCallback<
    SelectProps<typeof selectedAudioInputDeviceId>["onChange"]
  >((e) => {
    deviceSelectionDispatch({
      type: "UPDATE_SELECTED_DEVICE_ID",
      payload: {
        selectedAudioInputDeviceId: e.target.value,
      },
    });
  }, []);

  useEffect(() => {
    const videoInput = props.video
      ? videoInputs.find((d) => d.deviceId === selectedVideoInputDeviceId)
      : null;
    const audioInput = props.audio
      ? audioInputs.find((d) => d.deviceId === selectedAudioInputDeviceId)
      : null;
    props.onSelect({ video: videoInput, audio: audioInput });
  }, [
    props.video,
    props.audio,
    props.onSelect,
    videoInputs,
    audioInputs,
    selectedVideoInputDeviceId,
    selectedAudioInputDeviceId,
  ]);

  if (unavailable) {
    return <p>Unavailable</p>;
  }

  if (waitingForPermission) {
    return <p>Please allow the app to access the media devices</p>;
  }

  if (!permitted) {
    return <p>Not permitted</p>;
  }

  return (
    <div>
      {props.video && (
        <div>
          <VideoPreview deviceId={selectedVideoInputDeviceId} />
          {selectedVideoInputDeviceId && (
            <Select
              value={selectedVideoInputDeviceId}
              onChange={handleVideoInputChange}
            >
              {videoInputs.map((device) => (
                <MenuItem key={device.deviceId} value={device.deviceId}>
                  {device.label}
                </MenuItem>
              ))}
            </Select>
          )}
        </div>
      )}
      {props.audio && (
        <div>
          {/* TODO: AudioPreview */}
          {selectedAudioInputDeviceId && (
            <Select
              value={selectedAudioInputDeviceId}
              onChange={handleAudioInputChange}
            >
              {audioInputs.map((device) => (
                <MenuItem key={device.deviceId} value={device.deviceId}>
                  {device.label}
                </MenuItem>
              ))}
            </Select>
          )}
        </div>
      )}
    </div>
  );
};

export default DeviceSelect;
