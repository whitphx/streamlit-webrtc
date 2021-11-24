import React, { useState, useCallback } from "react";
import Box from "@mui/material/Box";
import Button, { ButtonProps } from "@mui/material/Button";
import DeviceSelectPopper from "./DeviceSelectPopper";
import { DevicesMap } from "./types";

interface DeviceSelectorProps {
  videoEnabled: boolean;
  audioEnabled: boolean;
  value: {
    video: MediaDeviceInfo | null;
    audio: MediaDeviceInfo | null;
  };
  onSelect: (
    video: MediaDeviceInfo | null,
    audio: MediaDeviceInfo | null
  ) => void;
}
const DeviceSelector: React.VFC<DeviceSelectorProps> = ({
  videoEnabled,
  audioEnabled,
  value,
  onSelect,
}) => {
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
    (video: MediaDeviceInfo | null, audio: MediaDeviceInfo | null) => {
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
          videoEnabled={videoEnabled}
          audioEnabled={audioEnabled}
          value={value}
          devicesMap={devicesMap}
          onSubmit={onSubmit}
        />
      )}
      <Button color="inherit" onClick={open ? onClose : onOpen}>
        Select device
      </Button>
    </Box>
  );
};

export default React.memo(DeviceSelector);
