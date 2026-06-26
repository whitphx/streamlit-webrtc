import React, { useCallback, useEffect, useMemo, useState } from "react";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import VideocamIcon from "@mui/icons-material/Videocam";
import VideocamOffIcon from "@mui/icons-material/VideocamOff";
import MicIcon from "@mui/icons-material/Mic";
import MicOffIcon from "@mui/icons-material/MicOff";
import { useTranslation } from "./translation/useTranslation";

type TrackKind = "video" | "audio";

interface InputMediaControlsProps {
  stream: MediaStream;
  disabled?: boolean;
}

function getTracks(stream: MediaStream, kind: TrackKind) {
  return kind === "video" ? stream.getVideoTracks() : stream.getAudioTracks();
}

function areTracksEnabled(stream: MediaStream, kind: TrackKind) {
  const tracks = getTracks(stream, kind);
  return tracks.length > 0 && tracks.every((track) => track.enabled);
}

function setTracksEnabled(
  stream: MediaStream,
  kind: TrackKind,
  enabled: boolean,
) {
  getTracks(stream, kind).forEach((track) => {
    track.enabled = enabled;
  });
}

function InputMediaControls({
  disabled = false,
  stream,
}: InputMediaControlsProps) {
  const hasVideo = stream.getVideoTracks().length > 0;
  const hasAudio = stream.getAudioTracks().length > 0;
  const [videoEnabled, setVideoEnabled] = useState(() =>
    areTracksEnabled(stream, "video"),
  );
  const [audioEnabled, setAudioEnabled] = useState(() =>
    areTracksEnabled(stream, "audio"),
  );

  useEffect(() => {
    setVideoEnabled(areTracksEnabled(stream, "video"));
    setAudioEnabled(areTracksEnabled(stream, "audio"));
  }, [stream]);

  const labels = {
    turnCameraOn: useTranslation("turn_camera_on") || "Turn camera on",
    turnCameraOff: useTranslation("turn_camera_off") || "Turn camera off",
    muteMicrophone: useTranslation("mute_microphone") || "Mute microphone",
    unmuteMicrophone:
      useTranslation("unmute_microphone") || "Unmute microphone",
  };

  const toggleVideo = useCallback(() => {
    const nextEnabled = !videoEnabled;
    setTracksEnabled(stream, "video", nextEnabled);
    setVideoEnabled(nextEnabled);
  }, [stream, videoEnabled]);

  const toggleAudio = useCallback(() => {
    const nextEnabled = !audioEnabled;
    setTracksEnabled(stream, "audio", nextEnabled);
    setAudioEnabled(nextEnabled);
  }, [stream, audioEnabled]);

  const controls = useMemo(
    () => [
      hasVideo && (
        <Tooltip
          key="video"
          title={videoEnabled ? labels.turnCameraOff : labels.turnCameraOn}
        >
          <IconButton
            aria-label={
              videoEnabled ? labels.turnCameraOff : labels.turnCameraOn
            }
            aria-pressed={!videoEnabled}
            color={videoEnabled ? "default" : "error"}
            disabled={disabled}
            onClick={toggleVideo}
            size="small"
            type="button"
          >
            {videoEnabled ? <VideocamIcon /> : <VideocamOffIcon />}
          </IconButton>
        </Tooltip>
      ),
      hasAudio && (
        <Tooltip
          key="audio"
          title={audioEnabled ? labels.muteMicrophone : labels.unmuteMicrophone}
        >
          <IconButton
            aria-label={
              audioEnabled ? labels.muteMicrophone : labels.unmuteMicrophone
            }
            aria-pressed={!audioEnabled}
            color={audioEnabled ? "default" : "error"}
            disabled={disabled}
            onClick={toggleAudio}
            size="small"
            type="button"
          >
            {audioEnabled ? <MicIcon /> : <MicOffIcon />}
          </IconButton>
        </Tooltip>
      ),
    ],
    [
      audioEnabled,
      disabled,
      hasAudio,
      hasVideo,
      labels.muteMicrophone,
      labels.turnCameraOff,
      labels.turnCameraOn,
      labels.unmuteMicrophone,
      toggleAudio,
      toggleVideo,
      videoEnabled,
    ],
  ).filter(Boolean);

  if (controls.length === 0) {
    return null;
  }

  return (
    <Stack direction="row" spacing={0.5}>
      {controls}
    </Stack>
  );
}

export default React.memo(InputMediaControls);
