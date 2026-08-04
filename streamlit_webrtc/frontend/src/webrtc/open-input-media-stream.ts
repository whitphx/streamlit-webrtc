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

function getAppliedDeviceId(
  spec: MediaStreamConstraints["video"],
): string | undefined {
  if (typeof spec !== "object" || spec == null) {
    return undefined;
  }
  const deviceId = spec.deviceId;
  // `compileMediaConstraints` applies a remembered ID as an `exact` object.
  // Anything else is the app's own constraint and not ours to drop.
  if (
    typeof deviceId === "object" &&
    deviceId != null &&
    !Array.isArray(deviceId) &&
    typeof deviceId.exact === "string"
  ) {
    return deviceId.exact;
  }
  return undefined;
}

// Only the remembered IDs that reached the compiled constraints are candidates
// for dropping: a kind the app disabled never received one, so that ID cannot
// be what the browser rejected, and an ID the app constrained itself is not
// ours to discard.
async function findUnavailableDeviceKinds(
  constraints: MediaStreamConstraints,
  rememberedDeviceIds: Record<InputDeviceKind, string | undefined>,
): Promise<InputDeviceKind[]> {
  const requestedDeviceIds = new Map<InputDeviceKind, string>();
  (Object.keys(MEDIA_DEVICE_KINDS) as InputDeviceKind[]).forEach((kind) => {
    const deviceId = rememberedDeviceIds[kind];
    if (
      deviceId != null &&
      getAppliedDeviceId(constraints[kind]) === deviceId
    ) {
      requestedDeviceIds.set(kind, deviceId);
    }
  });
  if (requestedDeviceIds.size === 0) {
    return [];
  }

  let devices: MediaDeviceInfo[];
  try {
    devices = await navigator.mediaDevices.enumerateDevices();
  } catch {
    // Without a device list there is no way to tell which ID went stale, so
    // treat every requested one as suspect rather than failing the start.
    return [...requestedDeviceIds.keys()];
  }

  return [...requestedDeviceIds]
    .filter(
      ([kind, deviceId]) =>
        !devices.some(
          (device) =>
            device.kind === MEDIA_DEVICE_KINDS[kind] &&
            device.deviceId === deviceId,
        ),
    )
    .map(([kind]) => kind);
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
    const unavailableDeviceKinds = await findUnavailableDeviceKinds(
      constraints,
      { video: videoDeviceId, audio: audioDeviceId },
    );
    if (unavailableDeviceKinds.length === 0) {
      // No remembered ID is at fault, so something else in the constraints is
      // unsatisfiable and retrying would open the wrong device rather than fix
      // anything.
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
