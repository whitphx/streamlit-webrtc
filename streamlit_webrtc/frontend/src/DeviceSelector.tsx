import React, { useState, useCallback } from "react";
import Box from "@material-ui/core/Box";
import Button, { ButtonProps } from "@material-ui/core/Button";
import FormControl from "@material-ui/core/FormControl";
import InputLabel from "@material-ui/core/InputLabel";
import Select, { SelectProps } from "@material-ui/core/Select";
import MenuItem from "@material-ui/core/MenuItem";
import Popper, { PopperProps } from "@material-ui/core/Popper";

interface DevicesMap {
  audio: MediaDeviceInfo[];
  video: MediaDeviceInfo[];
}

interface DeviceSelecterProps {
  labelId: SelectProps["labelId"];
  value: MediaDeviceInfo | null;
  devices: MediaDeviceInfo[];
  onChange: (device: MediaDeviceInfo | null) => void;
}
const DeviceSelecter = ({
  labelId,
  value,
  devices,
  onChange: onChangeProp,
}: DeviceSelecterProps) => {
  const onChange = useCallback<NonNullable<SelectProps["onChange"]>>(
    (e) => {
      const selected = devices.find((d) => d.deviceId === e.target.value);
      onChangeProp(selected || null);
    },
    [devices, onChangeProp]
  );

  if (devices.length === 0) {
    return (
      <Select value="" disabled>
        <option aria-label="None" value="" />
      </Select>
    );
  }

  if (value == null) {
    onChangeProp(devices[0]);
    return null;
  }

  return (
    <Select labelId={labelId} value={value.deviceId} onChange={onChange}>
      {devices.map((device) => (
        <MenuItem key={device.deviceId} value={device.deviceId}>
          {device.label}
        </MenuItem>
      ))}
    </Select>
  );
};

interface DeviceSelectPopperProps {
  open: boolean;
  anchorEl: PopperProps["anchorEl"];
  devicesMap: DevicesMap;
  onSubmit: (
    video: MediaDeviceInfo | null,
    audio: MediaDeviceInfo | null
  ) => void;
}
const DeviceSelectPopper = ({
  open,
  anchorEl,
  devicesMap,
  onSubmit,
}: DeviceSelectPopperProps) => {
  const [selectedVideo, setSelectedVideo] = useState<MediaDeviceInfo | null>(
    null
  );
  const [selectedAudio, setSelectedAudio] = useState<MediaDeviceInfo | null>(
    null
  );

  const onSubmitButton = useCallback(() => {
    onSubmit(selectedVideo, selectedAudio);
  }, [onSubmit, selectedVideo, selectedAudio]);

  return (
    <Popper open={open} anchorEl={anchorEl} placement="right">
      <Box style={{ backgroundColor: "white" }}>
        <FormControl>
          <InputLabel id="video-input-select">Video input</InputLabel>
          <DeviceSelecter
            labelId="video-input-select"
            devices={devicesMap.video}
            value={selectedVideo}
            onChange={setSelectedVideo}
          />
        </FormControl>
        <FormControl>
          <InputLabel id="audio-input-select">Audio input</InputLabel>
          <DeviceSelecter
            labelId="audio-input-select"
            devices={devicesMap.audio}
            value={selectedAudio}
            onChange={setSelectedAudio}
          />
        </FormControl>
        <Button onClick={onSubmitButton}>OK</Button>
      </Box>
    </Popper>
  );
};

interface DeviceSelectorProps {
  onSelect: (
    video: MediaDeviceInfo | null,
    audio: MediaDeviceInfo | null
  ) => void;
}
const DeviceSelector = ({ onSelect }: DeviceSelectorProps) => {
  const [open, setOpen] = useState(false);
  const [anchorEl, setAnchorEl] = React.useState<HTMLElement | null>(null);
  const [devicesMap, setDevicesMap] = useState<DevicesMap>();
  const [unavailable, setUnavailable] = useState(false);
  const onOpen = useCallback<NonNullable<ButtonProps["onClick"]>>((event) => {
    setAnchorEl(event.currentTarget);

    if (typeof navigator?.mediaDevices?.enumerateDevices !== "function") {
      setDevicesMap(undefined);
      setUnavailable(true);
      return;
    }

    navigator.mediaDevices.enumerateDevices().then((devices) => {
      const vidoeDevices = [];
      const audioDevices = [];
      for (const device of devices) {
        if (device.kind === "videoinput") {
          vidoeDevices.push(device);
        } else if (device.kind === "audioinput") {
          audioDevices.push(device);
        }
      }
      setDevicesMap({
        video: vidoeDevices,
        audio: audioDevices,
      });
      setOpen(true);
    });
  }, []);
  const onClose = useCallback(() => setOpen(false), []);

  const onSubmit = useCallback(
    (video, audio) => {
      setDevicesMap(undefined);
      setOpen(false);
      onSelect(video, audio);
    },
    [onSelect]
  );

  return (
    <Box>
      {unavailable && <p>Unavailable</p>}
      {devicesMap && (
        <DeviceSelectPopper
          open={open}
          anchorEl={anchorEl}
          devicesMap={devicesMap}
          onSubmit={onSubmit}
        />
      )}
      <Button onClick={open ? onClose : onOpen}>Select device</Button>
    </Box>
  );
};

export default React.memo(DeviceSelector);
