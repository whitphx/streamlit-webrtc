import { Streamlit } from "streamlit-component-lib";

export interface ComponentValue {
  playing: boolean;
  sdpOffer: string; // `Streamlit.setComponentValue` cannot "unset" the field by passing null or undefined, so an empty string will be used here for that purpose. // TODO: Create an issue
}

export function setComponentValue(componentValue: ComponentValue) {
  return Streamlit.setComponentValue(componentValue);
}
