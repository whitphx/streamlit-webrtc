import React, {
  useReducer,
  Reducer,
  useRef,
  useCallback,
  useState,
  useEffect,
} from "react";
import Select, { SelectProps } from "@mui/material/Select";
import MenuItem from "@mui/material/MenuItem";

function stopAllTracks(stream: MediaStream) {
  stream.getVideoTracks().forEach((track) => track.stop());
  stream.getAudioTracks().forEach((track) => track.stop());
}

interface DeviceSelectionState {
  unavailable: boolean;
  videoInputs: MediaDeviceInfo[];
  audioInputs: MediaDeviceInfo[];
  audioOutputs: MediaDeviceInfo[];
  // TODO: Add selectedAudioInputDeviceId and selectedAudioOutputDeviceId
  selectedVideoInputDeviceId: MediaDeviceInfo["deviceId"] | null;
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
  selectedVideoInputDeviceId: MediaDeviceInfo["deviceId"];
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
      };
    }
    case "UPDATE_DEVICES": {
      const devices = action.devices;
      const videoInputs = devices.filter((d) => d.kind === "videoinput");
      const audioInputs = devices.filter((d) => d.kind === "audioinput");
      const audioOutputs = devices.filter((d) => d.kind === "audiooutput");

      let selectedVideoInputDeviceId = state.selectedVideoInputDeviceId;
      const videoInputDeviceIds = videoInputs.map((d) => d.deviceId);
      if (!videoInputDeviceIds.includes(selectedVideoInputDeviceId)) {
        selectedVideoInputDeviceId =
          videoInputDeviceIds.length > 0 ? videoInputDeviceIds[0] : null;
      }

      return {
        ...state,
        videoInputs,
        audioInputs,
        audioOutputs,
        selectedVideoInputDeviceId,
      };
    }
    case "UPDATE_SELECTED_DEVICE_ID": {
      return {
        ...state,
        selectedVideoInputDeviceId: action.selectedVideoInputDeviceId,
      };
    }
  }
};

export interface DeviceSelectProps {
  video: boolean;
  audio: boolean;
}
const DeviceSelect: React.VFC<DeviceSelectProps> = (props) => {
  const [waitingForPermission, setWaitingForPermission] = useState(false);
  const [permitted, setPermitted] = useState(false);

  const [
    { unavailable, videoInputs, selectedVideoInputDeviceId },
    deviceSelectionDispatch,
  ] = useReducer(deviceSelectionReducer, {
    unavailable: false,
    videoInputs: [],
    audioInputs: [],
    audioOutputs: [],
    selectedVideoInputDeviceId: null,
  });

  const previewVideoRef = useRef<HTMLVideoElement>();

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

  useEffect(() => {
    if (selectedVideoInputDeviceId == null) {
      return;
    }

    let stream: MediaStream | undefined = undefined;
    navigator.mediaDevices
      .getUserMedia({ video: { deviceId: selectedVideoInputDeviceId } })
      .then((_stream) => {
        stream = _stream;

        previewVideoRef.current.srcObject = stream;
      });

    return () => {
      if (stream) {
        stopAllTracks(stream);
      }
    };
  }, [selectedVideoInputDeviceId]);

  const handleChange = useCallback<
    SelectProps<typeof selectedVideoInputDeviceId>["onChange"]
  >((e) => {
    deviceSelectionDispatch({
      type: "UPDATE_SELECTED_DEVICE_ID",
      selectedVideoInputDeviceId: e.target.value,
    });
  }, []);

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
      <video ref={previewVideoRef} autoPlay muted />
      {selectedVideoInputDeviceId && (
        <Select value={selectedVideoInputDeviceId} onChange={handleChange}>
          {videoInputs.map((device) => (
            <MenuItem key={device.deviceId} value={device.deviceId}>
              {device.label}
            </MenuItem>
          ))}
        </Select>
      )}
    </div>
  );
};

export default DeviceSelect;
