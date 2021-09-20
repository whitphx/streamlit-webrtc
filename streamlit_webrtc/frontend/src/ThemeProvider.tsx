import React from "react";
import { Theme } from "streamlit-component-lib";
import {
  createTheme,
  ThemeProvider as MuiThemeProvider,
} from "@material-ui/core/styles";
import chroma from "chroma-js";

interface StreamlitThemeProviderProps {
  theme: Theme | undefined;
}
export const ThemeProvider: React.VFC<
  React.PropsWithChildren<StreamlitThemeProviderProps>
> = (props) => {
  const stTheme = props.theme;

  const muiTheme = React.useMemo(() => {
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
  }, [stTheme]);

  if (muiTheme == null) {
    return <>{props.children}</>;
  }

  return <MuiThemeProvider theme={muiTheme}>{props.children}</MuiThemeProvider>;
};

export default ThemeProvider;
