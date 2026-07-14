import { compileMediaConstraints } from "../media-constraint";

export type InputDeviceKind = "video" | "audio";

const switchQueues = new WeakMap<
  Pick<RTCPeerConnection, "getSenders">,
  Partial<Record<InputDeviceKind, Promise<void>>>
>();

async function replaceInputDevice(
  peerConnection: Pick<RTCPeerConnection, "getSenders">,
  inputMediaStream: MediaStream,
  mediaStreamConstraints: MediaStreamConstraints | undefined,
  kind: InputDeviceKind,
  deviceId: MediaDeviceInfo["deviceId"],
): Promise<void> {
  const constraints = compileMediaConstraints(
    mediaStreamConstraints,
    kind === "video" ? deviceId : undefined,
    kind === "audio" ? deviceId : undefined,
  );
  if (kind === "video") {
    constraints.audio = false;
  } else {
    constraints.video = false;
  }

  const nextStream = await navigator.mediaDevices.getUserMedia(constraints);
  const nextTrack = nextStream.getTracks().find((track) => track.kind === kind);
  const sender = peerConnection
    .getSenders()
    .find((candidate) => candidate.track?.kind === kind);
  const previousTrack = sender?.track;

  if (nextTrack == null) {
    nextStream.getTracks().forEach((track) => track.stop());
    throw new Error(`No ${kind} track acquired`);
  }
  if (sender == null || previousTrack == null) {
    nextStream.getTracks().forEach((track) => track.stop());
    throw new Error(`No sender found for ${kind} track`);
  }

  nextTrack.enabled = previousTrack.enabled;
  try {
    await sender.replaceTrack(nextTrack);
  } catch (error) {
    nextStream.getTracks().forEach((track) => track.stop());
    throw error;
  }

  inputMediaStream.removeTrack(previousTrack);
  inputMediaStream.addTrack(nextTrack);
  previousTrack.stop();
  nextStream
    .getTracks()
    .filter((track) => track !== nextTrack)
    .forEach((track) => track.stop());
}

export function switchInputDevice(
  peerConnection: Pick<RTCPeerConnection, "getSenders">,
  inputMediaStream: MediaStream,
  mediaStreamConstraints: MediaStreamConstraints | undefined,
  kind: InputDeviceKind,
  deviceId: MediaDeviceInfo["deviceId"],
): Promise<void> {
  const queues = switchQueues.get(peerConnection) ?? {};
  switchQueues.set(peerConnection, queues);

  const previousSwitch = queues[kind] ?? Promise.resolve();
  const currentSwitch = previousSwitch
    .catch(() => undefined)
    .then(() =>
      replaceInputDevice(
        peerConnection,
        inputMediaStream,
        mediaStreamConstraints,
        kind,
        deviceId,
      ),
    );
  queues[kind] = currentSwitch;

  const removeCompletedSwitch = () => {
    if (queues[kind] === currentSwitch) {
      delete queues[kind];
    }
  };
  void currentSwitch.then(removeCompletedSwitch, removeCompletedSwitch);

  return currentSwitch;
}
