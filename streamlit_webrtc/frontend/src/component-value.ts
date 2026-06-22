import { Streamlit } from "streamlit-component-lib";

export interface FrontendEvent {
  id: string;
  type: "connection_lost" | "track_ended";
  reason: string;
  at: number;
}

export interface ComponentValue {
  playing: boolean;
  sdpOffer: RTCSessionDescriptionInit | ""; // `Streamlit.setComponentValue` cannot "unset" the field by passing null or undefined, so an empty string will be used here for that purpose. // TODO: Create an issue
  iceCandidates: Record<string, RTCIceCandidateInit>;
  frontendEvent?: FrontendEvent;
}

export function setComponentValue(componentValue: ComponentValue) {
  return Streamlit.setComponentValue(componentValue);
}
