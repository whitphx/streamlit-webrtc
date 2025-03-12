import React from "react";
import { Theme } from "streamlit-component-lib";
import { useRenderData } from "streamlit-component-lib-react-hooks";
import {
  createTheme,
  ThemeProvider as MuiThemeProvider,
} from "@mui/material/styles";
import chroma from "chroma-js";

export const ThemeProvider: React.VFC<React.PropsWithChildren<unknown>> = (
  props,
) => {
  const { theme: stTheme } = useRenderData();

  const stThemeJson = JSON.stringify(stTheme);
  const muiTheme = React.useMemo(() => {
    const stTheme: Theme = JSON.parse(stThemeJson);
    if (stTheme == null) {
      return undefined;
    }

    const textColorScale = chroma
      .scale([stTheme.textColor, stTheme.backgroundColor])
      .mode("lab");

    return createTheme({
      palette: {
        primary: {
          main: stTheme.primaryColor,
        },
        background: {
          default: stTheme.backgroundColor,
          paper: stTheme.secondaryBackgroundColor,
        },
        text: {
          primary: stTheme.textColor,
          secondary: textColorScale(0.1).hex(),
          disabled: textColorScale(0.5).hex(),
        },
      },
      typography: {
        fontFamily: stTheme.font,
      },
    });
  }, [stThemeJson]);

  if (muiTheme == null) {
    return <>{props.children}</>;
  }

  return <MuiThemeProvider theme={muiTheme}>{props.children}</MuiThemeProvider>;
};

export default ThemeProvider;
