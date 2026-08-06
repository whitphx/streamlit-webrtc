import React, { useEffect, useRef, useState } from "react";
import Box from "@mui/material/Box";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import { styled } from "@mui/material/styles";
import ArrowDropDownIcon from "@mui/icons-material/ArrowDropDown";
import VideocamIcon from "@mui/icons-material/Videocam";
import VideocamOffIcon from "@mui/icons-material/VideocamOff";
import MicIcon from "@mui/icons-material/Mic";
import MicOffIcon from "@mui/icons-material/MicOff";
import { useTranslation } from "./translation/useTranslation";
import { useMediaInputDevices } from "./use-media-input-devices";
import type { InputDeviceKind } from "./webrtc";

type DeviceIds = Partial<Record<InputDeviceKind, MediaDeviceInfo["deviceId"]>>;

interface InputMediaControlsProps {
  stream: MediaStream;
  disabled?: boolean;
  onSelectDevice: (
    kind: InputDeviceKind,
    deviceId: MediaDeviceInfo["deviceId"],
  ) => Promise<void>;
}

function getTracks(stream: MediaStream, kind: InputDeviceKind) {
  return kind === "video" ? stream.getVideoTracks() : stream.getAudioTracks();
}

// The device behind the track that is actually feeding the connection. A
// remembered selection cannot answer this: a track ends when its device is
// unplugged and stays ended when the same device is plugged back in, ID and
// all, so an ID that appears in the device list again still names nothing live.
function getLiveDeviceId(
  stream: MediaStream,
  kind: InputDeviceKind,
): MediaDeviceInfo["deviceId"] | undefined {
  const track = getTracks(stream, kind).find(
    (candidate) => candidate.readyState === "live",
  );
  return track?.getSettings?.().deviceId;
}

function areTracksEnabled(stream: MediaStream, kind: InputDeviceKind) {
  const tracks = getTracks(stream, kind);
  return tracks.length > 0 && tracks.every((track) => track.enabled);
}

function setTracksEnabled(
  stream: MediaStream,
  kind: InputDeviceKind,
  enabled: boolean,
) {
  getTracks(stream, kind).forEach((track) => {
    track.enabled = enabled;
  });
}

// Device labels are only populated once media permission is granted, which it
// is whenever these controls are on screen, so this is a safety net.
function fallbackDeviceLabel(kind: InputDeviceKind, index: number) {
  return `${kind === "video" ? "Camera" : "Microphone"} ${index + 1}`;
}

// The picker is a transparent native `<select>` covering the arrow icon.
// Streamlit pins this iframe's height to its content, so a dropdown drawn in
// the document would be clipped by the frame, while a native one is drawn by
// the browser outside it (and opens as a native picker on mobile).
const DeviceSelectOverlay = styled("select")({
  position: "absolute",
  inset: 0,
  width: "100%",
  height: "100%",
  margin: 0,
  padding: 0,
  border: "none",
  appearance: "none",
  opacity: 0,
  // Native controls do not inherit the page font, and iOS Safari zooms the
  // page when a focused one is under 16px.
  fontSize: 16,
  cursor: "pointer",
  "&:disabled": {
    cursor: "default",
  },
});

interface InputDeviceSelectProps {
  kind: InputDeviceKind;
  label: string;
  devices: MediaDeviceInfo[];
  selectedDeviceId: MediaDeviceInfo["deviceId"] | undefined;
  disabled: boolean;
  onSelect: (deviceId: MediaDeviceInfo["deviceId"]) => void;
}
function InputDeviceSelect({
  kind,
  label,
  devices,
  selectedDeviceId,
  disabled,
  onSelect,
}: InputDeviceSelectProps) {
  const currentDevice = devices.find(
    (device) => device.deviceId === selectedDeviceId,
  );
  // Only the absence of anything to switch to hides the picker. The live
  // device going missing does not qualify: an unplugged camera is when the
  // picker matters most, and where playback is driven by the app rather than
  // the user it is the only control left to recover through.
  const hasAlternative = devices.some(
    (device) => device.deviceId !== selectedDeviceId,
  );
  if (!hasAlternative) {
    return null;
  }

  return (
    <Tooltip title={currentDevice?.label || label}>
      <Box
        sx={{
          position: "relative",
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          // WCAG 2.2 SC 2.5.8 sets the minimum pointer target at 24 by 24.
          width: 24,
          height: 30,
          borderRadius: 1,
          // The same palette entries `IconButton` uses, so the arrow and the
          // toggle it sits against read as one control.
          color: disabled ? "action.disabled" : "action.active",
          "&:focus-within": {
            outline: "2px solid",
            outlineColor: "primary.main",
          },
          "@media (hover: hover)": {
            "&:hover": {
              backgroundColor: disabled ? undefined : "action.hover",
            },
          },
        }}
      >
        <ArrowDropDownIcon fontSize="small" />
        <DeviceSelectOverlay
          aria-label={label}
          // Empty once the live device is gone, so the native picker marks
          // none of the survivors as the one in use.
          value={currentDevice?.deviceId ?? ""}
          disabled={disabled}
          onChange={(e) => onSelect(e.target.value)}
        >
          {currentDevice == null && (
            // Something has to hold the empty value: a select with no option
            // selected falls back to the first one it can, which would name a
            // device that is not the one in use.
            <option value="" disabled>
              {label}
            </option>
          )}
          {devices.map((device, index) => (
            <option key={device.deviceId} value={device.deviceId}>
              {device.label || fallbackDeviceLabel(kind, index)}
            </option>
          ))}
        </DeviceSelectOverlay>
      </Box>
    </Tooltip>
  );
}

function InputMediaControls({
  disabled = false,
  stream,
  onSelectDevice,
}: InputMediaControlsProps) {
  const hasVideo = stream.getVideoTracks().length > 0;
  const hasAudio = stream.getAudioTracks().length > 0;
  const [enabled, setEnabled] = useState(() => ({
    video: areTracksEnabled(stream, "video"),
    audio: areTracksEnabled(stream, "audio"),
  }));
  // A switch only reaches the track it is opening when it succeeds, so until
  // then the picker shows the device being waited on rather than the one still
  // live.
  const [pendingDeviceIds, setPendingDeviceIds] = useState<DeviceIds>({});
  const selectionRequestIdsRef = useRef({ video: 0, audio: 0 });

  useEffect(() => {
    setEnabled({
      video: areTracksEnabled(stream, "video"),
      audio: areTracksEnabled(stream, "audio"),
    });
    // A switch in flight was asked for on the stream being replaced, so the
    // device it is waiting on describes nothing here. Its own completion is
    // already ignored once a later request exists, so dropping the display
    // value is all this needs.
    setPendingDeviceIds({});
  }, [stream]);

  const labels = {
    turnCameraOn: useTranslation("turn_camera_on") || "Turn camera on",
    turnCameraOff: useTranslation("turn_camera_off") || "Turn camera off",
    muteMicrophone: useTranslation("mute_microphone") || "Mute microphone",
    unmuteMicrophone:
      useTranslation("unmute_microphone") || "Unmute microphone",
    selectCamera: useTranslation("select_camera") || "Select camera",
    selectMicrophone:
      useTranslation("select_microphone") || "Select microphone",
  };

  const toggle = (kind: InputDeviceKind) => {
    const nextEnabled = !enabled[kind];
    setTracksEnabled(stream, kind, nextEnabled);
    setEnabled((prev) => ({ ...prev, [kind]: nextEnabled }));
  };

  // These controls only exist while the input stream is live, so enumerating
  // from here happens with media permission granted, which is what makes the
  // browser hand over device labels at all.
  const { devices } = useMediaInputDevices();
  const selectDevice = (
    kind: InputDeviceKind,
    deviceId: MediaDeviceInfo["deviceId"],
  ) => {
    const requestId = ++selectionRequestIdsRef.current[kind];
    setPendingDeviceIds((prev) => ({ ...prev, [kind]: deviceId }));
    const settle = () => {
      // A later pick is already in flight and owns the displayed value.
      if (selectionRequestIdsRef.current[kind] !== requestId) {
        return;
      }
      setPendingDeviceIds((prev) => {
        const next = { ...prev };
        delete next[kind];
        return next;
      });
    };
    onSelectDevice(kind, deviceId).then(settle, settle);
  };

  const controls = [
    {
      kind: "video" as const,
      present: hasVideo,
      onIcon: <VideocamIcon />,
      offIcon: <VideocamOffIcon />,
      enableLabel: labels.turnCameraOn,
      disableLabel: labels.turnCameraOff,
      selectLabel: labels.selectCamera,
      devices: devices.video,
      selectedDeviceId:
        pendingDeviceIds.video ?? getLiveDeviceId(stream, "video"),
    },
    {
      kind: "audio" as const,
      present: hasAudio,
      onIcon: <MicIcon />,
      offIcon: <MicOffIcon />,
      enableLabel: labels.unmuteMicrophone,
      disableLabel: labels.muteMicrophone,
      selectLabel: labels.selectMicrophone,
      devices: devices.audio,
      selectedDeviceId:
        pendingDeviceIds.audio ?? getLiveDeviceId(stream, "audio"),
    },
  ].filter((control) => control.present);

  if (controls.length === 0) {
    return null;
  }

  return (
    <Stack direction="row" spacing={1}>
      {controls.map((control) => {
        const isEnabled = enabled[control.kind];
        const toggleLabel = isEnabled
          ? control.disableLabel
          : control.enableLabel;
        return (
          <Box key={control.kind} display="inline-flex" alignItems="center">
            <Tooltip title={toggleLabel}>
              <IconButton
                aria-label={toggleLabel}
                aria-pressed={!isEnabled}
                color={isEnabled ? "default" : "error"}
                disabled={disabled}
                onClick={() => toggle(control.kind)}
                size="small"
                type="button"
              >
                {isEnabled ? control.onIcon : control.offIcon}
              </IconButton>
            </Tooltip>
            <InputDeviceSelect
              kind={control.kind}
              label={control.selectLabel}
              devices={control.devices}
              selectedDeviceId={control.selectedDeviceId}
              // Switching opens the device, which lights its indicator. Doing
              // that under a control the user has just turned off would say
              // the opposite of what the screen says.
              disabled={disabled || !isEnabled}
              onSelect={(deviceId) => selectDevice(control.kind, deviceId)}
            />
          </Box>
        );
      })}
    </Stack>
  );
}

export default React.memo(InputMediaControls);
