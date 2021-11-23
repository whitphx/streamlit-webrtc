import React from "react";
import { useRenderData } from "streamlit-component-lib-react-hooks";
import {
  ThemeProvider as MuiThemeProvider,
  createTheme,
} from "@mui/material/styles";
import chroma from "chroma-js";

interface StreamlitThemeProviderProps {}
export const ThemeProvider: React.VFC<
  React.PropsWithChildren<StreamlitThemeProviderProps>
> = (props) => {
  const { theme: stTheme } = useRenderData();

  const muiTheme = React.useMemo(() => {
    if (stTheme == null) {
      return createTheme({
        components: {
          MuiCssBaseline: {
            styleOverrides: {
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
