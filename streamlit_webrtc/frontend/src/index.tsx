import React from "react";
import ReactDOM from "react-dom";
import { ThemeProvider } from "./ThemeProvider";
import CssBaseline from "@mui/material/CssBaseline";
import { StreamlitProvider } from "streamlit-component-lib-react-hooks";
import TranslationProvider from "./translation/TranslationProvider";
import WebRtcStreamer from "./WebRtcStreamer";

ReactDOM.render(
  <React.StrictMode>
    <StreamlitProvider>
      <TranslationProvider>
        <ThemeProvider>
          <CssBaseline />
          <WebRtcStreamer />
        </ThemeProvider>
      </TranslationProvider>
    </StreamlitProvider>
  </React.StrictMode>,
  document.getElementById("root")
);
