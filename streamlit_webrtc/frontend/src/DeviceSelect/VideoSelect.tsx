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
  devices: MediaDeviceInfo[];
  selectedDeviceId: MediaDeviceInfo["deviceId"] | null;
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
  selectedDeviceId: MediaDeviceInfo["deviceId"];
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
        devices: [],
        selectedDeviceId: null,
      };
    }
    case "UPDATE_DEVICES": {
      const devices = action.devices;
      const deviceIds = devices.map((device) => device.deviceId);
      if (!deviceIds.includes(state.selectedDeviceId)) {
        const selectedDeviceId =
          devices.length > 0 ? devices[0].deviceId : null;
        return {
          ...state,
          devices,
          selectedDeviceId,
        };
      }
      return {
        ...state,
        devices: action.devices,
      };
    }
    case "UPDATE_SELECTED_DEVICE_ID": {
      return {
        ...state,
        selectedDeviceId: action.selectedDeviceId,
      };
    }
  }
};

const VideoSelect: React.VFC = () => {
  const [waitingForPermission, setWaitingForPermission] = useState(false);
  const [permitted, setPermitted] = useState(false);

  const [{ unavailable, devices, selectedDeviceId }, deviceSelectionDispatch] =
    useReducer(deviceSelectionReducer, {
      unavailable: false,
      devices: [],
      selectedDeviceId: null,
    });

  const previewVideoRef = useRef<HTMLVideoElement>();

  // Ref: https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/ondevicechange#example
  const updateDeviceList = useCallback(() => {
    if (typeof navigator?.mediaDevices?.enumerateDevices !== "function") {
      deviceSelectionDispatch({ type: "SET_UNAVAILABLE" });
      return;
    }

    return navigator.mediaDevices.enumerateDevices().then((devices) => {
      const videoInputDevices = devices.filter(
        (device) => device.kind === "videoinput"
      );
      deviceSelectionDispatch({
        type: "UPDATE_DEVICES",
        devices: videoInputDevices,
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
      .getUserMedia({ video: true, audio: false })
      .then((stream) => {
        stopAllTracks(stream);

        setPermitted(true);
      })
      .finally(() => setWaitingForPermission(false));
  }, [updateDeviceList]);

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
    if (selectedDeviceId == null) {
      return;
    }

    let stream: MediaStream | undefined = undefined;
    navigator.mediaDevices
      .getUserMedia({ video: { deviceId: selectedDeviceId } })
      .then((_stream) => {
        stream = _stream;

        previewVideoRef.current.srcObject = stream;
      });

    return () => {
      if (stream) {
        stopAllTracks(stream);
      }
    };
  }, [selectedDeviceId]);

  const handleChange = useCallback<
    SelectProps<typeof selectedDeviceId>["onChange"]
  >((e) => {
    deviceSelectionDispatch({
      type: "UPDATE_SELECTED_DEVICE_ID",
      selectedDeviceId: e.target.value,
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
      {selectedDeviceId && (
        <Select value={selectedDeviceId} onChange={handleChange}>
          {devices.map((device) => (
            <MenuItem key={device.deviceId} value={device.deviceId}>
              {device.label}
            </MenuItem>
          ))}
        </Select>
      )}
    </div>
  );
};

export default VideoSelect;
