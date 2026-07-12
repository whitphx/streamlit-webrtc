export function compileMediaConstraints(
  src: MediaStreamConstraints | undefined,
  videoDeviceId: string | undefined,
  audioDeviceId: string | undefined,
): MediaStreamConstraints {
  const constraints: MediaStreamConstraints = { ...src };

  // `exact` is required here: a bare deviceId is only an "ideal" hint that
  // browsers may ignore, silently falling back to the default camera
  // (observed with macOS Continuity Camera).
  // Ref: https://developer.mozilla.org/en-US/docs/Web/API/MediaTrackConstraints#deviceid
  if (videoDeviceId) {
    if (constraints.video === true) {
      constraints.video = {
        deviceId: { exact: videoDeviceId },
      };
    } else if (
      typeof constraints.video === "object" ||
      constraints.video == null
    ) {
      constraints.video = {
        ...constraints.video,
        deviceId: { exact: videoDeviceId },
      };
    }
  }

  if (audioDeviceId) {
    if (constraints.audio === true) {
      constraints.audio = {
        deviceId: { exact: audioDeviceId },
      };
    } else if (
      typeof constraints.audio === "object" ||
      constraints.audio == null
    ) {
      constraints.audio = {
        ...constraints.audio,
        deviceId: { exact: audioDeviceId },
      };
    }
  }

  return constraints;
}

interface MediaUsage {
  videoEnabled: boolean;
  audioEnabled: boolean;
}
export function getMediaUsage(
  constraintsFromPython?: MediaStreamConstraints,
): MediaUsage {
  const videoEnabled = constraintsFromPython
    ? !!constraintsFromPython.video
    : true;
  const audioEnabled = constraintsFromPython
    ? !!constraintsFromPython.audio
    : true;

  return { videoEnabled, audioEnabled };
}
