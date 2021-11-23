import React from "react";
import ReactDOM from "react-dom";
import { ThemeProvider } from "./ThemeProvider";
import CssBaseline from "@mui/material/CssBaseline";
import { StreamlitProvider } from "streamlit-component-lib-react-hooks";
import WebRtcStreamer from "./WebRtcStreamer";

ReactDOM.render(
  <React.StrictMode>
    <StreamlitProvider>
      <ThemeProvider>
        <CssBaseline />
        <WebRtcStreamer />
      </ThemeProvider>
    </StreamlitProvider>
  </React.StrictMode>,
  document.getElementById("root")
);
