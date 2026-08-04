import { compileMediaConstraints } from "../media-constraint";
import type { InputDeviceKind } from "./switch-input-device";

const MEDIA_DEVICE_KINDS: Record<InputDeviceKind, MediaDeviceKind> = {
  video: "videoinput",
  audio: "audioinput",
};

export interface OpenedInputMedia {
  stream: MediaStream;
  // Kinds whose requested device ID no longer resolves, so the stream was
  // opened without it. The caller owns the stored selection and is the one
  // that can replace the dead ID.
  unavailableDeviceKinds: InputDeviceKind[];
}

function isOverconstrainedError(error: unknown): boolean {
  return (
    typeof error === "object" &&
    error != null &&
    (error as { name?: unknown }).name === "OverconstrainedError"
  );
}

async function findUnavailableDeviceKinds(
  requestedDeviceIds: Record<InputDeviceKind, string | undefined>,
): Promise<InputDeviceKind[]> {
  const requestedKinds = (
    Object.keys(requestedDeviceIds) as InputDeviceKind[]
  ).filter((kind) => requestedDeviceIds[kind] != null);
  if (requestedKinds.length === 0) {
    return [];
  }

  let devices: MediaDeviceInfo[];
  try {
    devices = await navigator.mediaDevices.enumerateDevices();
  } catch {
    // Without a device list there is no way to tell which ID went stale, so
    // treat every requested one as suspect rather than failing the start.
    return requestedKinds;
  }

  return requestedKinds.filter(
    (kind) =>
      !devices.some(
        (device) =>
          device.kind === MEDIA_DEVICE_KINDS[kind] &&
          device.deviceId === requestedDeviceIds[kind],
      ),
  );
}

// Returns null when the compiled constraints ask for no media at all, in which
// case there is nothing to capture and no permission to request.
export async function openInputMediaStream(
  mediaStreamConstraints: MediaStreamConstraints | undefined,
  videoDeviceId: MediaDeviceInfo["deviceId"] | undefined,
  audioDeviceId: MediaDeviceInfo["deviceId"] | undefined,
): Promise<OpenedInputMedia | null> {
  const constraints = compileMediaConstraints(
    mediaStreamConstraints,
    videoDeviceId,
    audioDeviceId,
  );
  console.debug("MediaStreamConstraints:", constraints);

  if (!constraints.audio && !constraints.video) {
    return null;
  }

  if (navigator.mediaDevices == null) {
    // Ref: https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia#privacy_and_security
    // > A secure context is, in short, a page loaded using HTTPS or the file:/// URL scheme, or a page loaded from localhost.
    throw new Error(
      "navigator.mediaDevices is undefined. It seems the current document is not loaded securely.",
    );
  }
  if (navigator.mediaDevices.getUserMedia == null) {
    throw new Error("getUserMedia is not implemented in this browser");
  }

  try {
    return {
      stream: await navigator.mediaDevices.getUserMedia(constraints),
      unavailableDeviceKinds: [],
    };
  } catch (error: unknown) {
    if (!isOverconstrainedError(error)) {
      throw error;
    }

    // A remembered device ID outlives the device it names: browsers reissue
    // IDs when site data or the camera permission is reset, and the device
    // itself can be unplugged. Those IDs go in as `exact` constraints, so a
    // dead one rejects the whole capture instead of degrading.
    const unavailableDeviceKinds = await findUnavailableDeviceKinds({
      video: videoDeviceId,
      audio: audioDeviceId,
    });
    if (unavailableDeviceKinds.length === 0) {
      // Every requested device is present, so something else in the
      // constraints is unsatisfiable and dropping the IDs would open the
      // wrong device rather than fix anything.
      throw error;
    }

    // Only the dead IDs are dropped, so an unplugged camera does not also
    // discard a microphone selection that is still valid.
    const fallbackConstraints = compileMediaConstraints(
      mediaStreamConstraints,
      unavailableDeviceKinds.includes("video") ? undefined : videoDeviceId,
      unavailableDeviceKinds.includes("audio") ? undefined : audioDeviceId,
    );
    console.debug(
      "Retrying with fallback MediaStreamConstraints:",
      fallbackConstraints,
      "unavailable devices:",
      unavailableDeviceKinds,
    );
    return {
      stream: await navigator.mediaDevices.getUserMedia(fallbackConstraints),
      unavailableDeviceKinds,
    };
  }
}
