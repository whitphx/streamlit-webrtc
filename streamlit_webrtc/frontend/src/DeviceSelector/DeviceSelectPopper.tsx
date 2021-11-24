import React, { useState, useCallback, useRef, useEffect } from "react";
import { Streamlit } from "streamlit-component-lib";
import Button from "@mui/material/Button";
import FormControl from "@mui/material/FormControl";
import InputLabel from "@mui/material/InputLabel";
import Popper, { PopperProps } from "@mui/material/Popper";
import Paper from "@mui/material/Paper";
import { styled } from "@mui/material/styles";
import DeviceSelecter from "./DeviceSelector";
import { DevicesMap } from "./types";

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
const DeviceSelectPopper: React.VFC<DeviceSelectPopperProps> = ({
  open,
  anchorEl,
  videoEnabled,
  audioEnabled,
  value,
  devicesMap,
  onSubmit,
}) => {
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

export default DeviceSelectPopper;
