import React from "react";
import { createRoot } from "react-dom/client";
import { ThemeProvider } from "./ThemeProvider";
import CssBaseline from "@mui/material/CssBaseline";
import { StreamlitProvider } from "streamlit-component-lib-react-hooks";
import TranslationProvider from "./translation/TranslationProvider";
import WebRtcStreamer from "./WebRtcStreamer";

const container = document.getElementById("root");
if (!container) throw new Error("Failed to find the root element");

const root = createRoot(container);
root.render(
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
);
