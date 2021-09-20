export type WebRtcMode = "RECVONLY" | "SENDONLY" | "SENDRECV";
export const isWebRtcMode = (val: unknown): val is WebRtcMode =>
  val === "RECVONLY" || val === "SENDONLY" || val === "SENDRECV";
export const isReceivable = (mode: WebRtcMode): boolean =>
  mode === "SENDRECV" || mode === "RECVONLY";
export const isTransmittable = (mode: WebRtcMode): boolean =>
  mode === "SENDRECV" || mode === "SENDONLY";

export const useWebRtc = () => {};
