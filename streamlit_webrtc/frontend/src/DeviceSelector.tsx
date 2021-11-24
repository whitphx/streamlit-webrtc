import React, { useState, useCallback, useRef, useEffect } from "react";
import { Streamlit } from "streamlit-component-lib";
import Box from "@mui/material/Box";
import Button, { ButtonProps } from "@mui/material/Button";
import FormControl from "@mui/material/FormControl";
import InputLabel from "@mui/material/InputLabel";
import Select, { SelectProps } from "@mui/material/Select";
import MenuItem from "@mui/material/MenuItem";
import Popper, { PopperProps } from "@mui/material/Popper";
import Paper from "@mui/material/Paper";
import { styled } from "@mui/material/styles";

const StyledPaper = styled(Paper)(({ theme }) => ({
  padding: theme.spacing(2),
}));
const StyledFormControl = styled(FormControl)(({ theme }) => ({
  maxWidth: "80vw",
  margin: theme.spacing(1),
  minWidth: 120,
  display: "flex",
}));
const StyledFormButtonControl = styled(FormControl)(({ theme }) => ({
  margin: theme.spacing(2),
  marginBottom: theme.spacing(1),
  minWidth: 120,
  display: "flex",
}));
const StyledSelect = styled(Select)(({ theme }) => ({
  marginTop: theme.spacing(2),
}));

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
    setImmediate(() => onChangeProp(devices[0]));
    return null;
  }

  return (
    <StyledSelect labelId={labelId} value={value.deviceId} onChange={onChange}>
      {devices.map((device) => (
        <MenuItem key={device.deviceId} value={device.deviceId}>
          {device.label}
        </MenuItem>
      ))}
    </StyledSelect>
  );
};

interface DeviceSelectPopperProps {
  open: boolean;
  anchorEl: PopperProps["anchorEl"];
  videoEnabled: boolean;
  audioEnabled: boolean;
  value: {
    video: MediaDeviceInfo | null;
    audio: MediaDeviceInfo | null;
  };
  devicesMap: DevicesMap;
  onSubmit: (
    video: MediaDeviceInfo | null,
    audio: MediaDeviceInfo | null
  ) => void;
}
const DeviceSelectPopper = ({
  open,
  anchorEl,
  videoEnabled,
  audioEnabled,
  value,
  devicesMap,
  onSubmit,
}: DeviceSelectPopperProps) => {
  const [selectedVideo, setSelectedVideo] = useState<MediaDeviceInfo | null>(
    null
  );
  const [selectedAudio, setSelectedAudio] = useState<MediaDeviceInfo | null>(
    null
  );

  useEffect(() => {
    setSelectedVideo(
      devicesMap.video.find((d) => d.deviceId === value.video?.deviceId) || null
    );
    setSelectedAudio(
      devicesMap.audio.find((d) => d.deviceId === value.audio?.deviceId) || null
    );
  }, [devicesMap, value]);

  const handleSubmit = useCallback<
    NonNullable<React.ComponentProps<"form">["onSubmit"]>
  >(
    (e) => {
      e.preventDefault();
      onSubmit(
        videoEnabled ? selectedVideo : null,
        audioEnabled ? selectedAudio : null
      );
    },
    [onSubmit, videoEnabled, audioEnabled, selectedVideo, selectedAudio]
  );

  const originalBodyHeightRef = useRef<string>();
  const popperRefFn = useCallback((popper: HTMLDivElement | null) => {
    // Manage <body>'s height reacting to popper appearance.
    if (popper) {
      setTimeout(() => {
        const body = document.getElementsByTagName("body")[0];
        originalBodyHeightRef.current = body.style.height;

        const style = window.getComputedStyle(popper);
        const matrix = new WebKitCSSMatrix(style.transform);
        const translateY = matrix.m42;

        const scrollBottom = translateY + popper.getBoundingClientRect().height;
        if (scrollBottom > document.body.scrollHeight) {
          body.style.height = `${scrollBottom}px`;
          Streamlit.setFrameHeight();
        }
      }, 0);
    } else {
      setTimeout(() => {
        const body = document.getElementsByTagName("body")[0];
        if (originalBodyHeightRef.current != null) {
          body.style.height = originalBodyHeightRef.current;
        }
        Streamlit.setFrameHeight();
      }, 0);
    }
  }, []);

  return (
    <Popper
      ref={popperRefFn}
      open={open}
      anchorEl={anchorEl}
      placement="left-end"
    >
      <StyledPaper>
        <form onSubmit={handleSubmit}>
          {videoEnabled && (
            <StyledFormControl>
              <InputLabel id="video-input-select">Video input</InputLabel>
              <DeviceSelecter
                labelId="video-input-select"
                devices={devicesMap.video}
                value={selectedVideo}
                onChange={setSelectedVideo}
              />
            </StyledFormControl>
          )}
          {audioEnabled && (
            <StyledFormControl>
              <InputLabel id="audio-input-select">Audio input</InputLabel>
              <DeviceSelecter
                labelId="audio-input-select"
                devices={devicesMap.audio}
                value={selectedAudio}
                onChange={setSelectedAudio}
              />
            </StyledFormControl>
          )}
          <StyledFormButtonControl>
            <Button type="submit" variant="contained" color="primary">
              OK
            </Button>
          </StyledFormButtonControl>
        </form>
      </StyledPaper>
    </Popper>
  );
};

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
const DeviceSelector = ({
  videoEnabled,
  audioEnabled,
  value,
  onSelect,
}: DeviceSelectorProps) => {
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
      <Button onClick={open ? onClose : onOpen}>Select device</Button>
    </Box>
  );
};

export default React.memo(DeviceSelector);
