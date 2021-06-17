export function compileMediaConstraints(
  src: MediaStreamConstraints | undefined,
  videoDeviceId: string | undefined,
  audioDeviceId: string | undefined
): MediaStreamConstraints {
  const constraints = src || {};

  if (videoDeviceId) {
    if (constraints.video === true) {
      constraints.video = {
        deviceId: videoDeviceId,
      };
    } else if (
      typeof constraints.video === "object" ||
      constraints.video == null
    ) {
      constraints.video = {
        ...constraints.video,
        deviceId: videoDeviceId,
      };
    }
  }

  if (audioDeviceId) {
    if (constraints.audio === true) {
      constraints.audio = {
        deviceId: audioDeviceId,
      };
    } else if (
      typeof constraints.audio === "object" ||
      constraints.audio == null
    ) {
      constraints.audio = {
        ...constraints.audio,
        deviceId: audioDeviceId,
      };
    }
  }

  return constraints;
}

interface MediaUsage {
  videoEnabled: boolean;
  audioEnabled: boolean;
}
export function getMediaUsage(constraintsFromPython: any): MediaUsage {
  const videoEnabled = constraintsFromPython
    ? !!constraintsFromPython.video
    : true;
  const audioEnabled = constraintsFromPython
    ? !!constraintsFromPython.audio
    : true;

  return { videoEnabled, audioEnabled };
}
