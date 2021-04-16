import React from "react";
import { Theme } from "streamlit-component-lib";
import {
  createMuiTheme,
  ThemeProvider as MuiThemeProvider,
} from "@material-ui/core/styles";

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

    return createMuiTheme({
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
