import { Streamlit } from "streamlit-component-lib";

interface ComponentValue {
  sdpOffer: string | null;
  playing: boolean;
  signalling: boolean;
}

// A wrapper of Streamlit.setComponentValue with type annotations
export function setComponentValue(value: ComponentValue) {
  return Streamlit.setComponentValue(value);
}
