import React from "react";
import ReactDOM from "react-dom";
import { createTheme, ThemeProvider } from "@material-ui/core/styles";
import CssBaseline from "@material-ui/core/CssBaseline";
import { StreamlitProvider } from "streamlit-component-lib-react-hooks";
import WebRtcStreamer from "./WebRtcStreamer";

const theme = createTheme({
  overrides: {
    MuiCssBaseline: {
      "@global": {
        body: {
          // Unset the background-color since <CssBaseLine /> applies the default Material Design background color
          // (https://material-ui.com/components/css-baseline/#approach),
          // which however does not match the Streamlit's background.
          backgroundColor: "initial",
        },
      },
    },
  },
});

ReactDOM.render(
  <React.StrictMode>
    <StreamlitProvider>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <WebRtcStreamer />
      </ThemeProvider>
    </StreamlitProvider>
  </React.StrictMode>,
  document.getElementById("root")
);
