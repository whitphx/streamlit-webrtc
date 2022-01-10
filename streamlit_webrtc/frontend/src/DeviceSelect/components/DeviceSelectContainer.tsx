import React from "react";
import Stack from "@mui/material/Stack";
import { useTheme } from "@mui/material/styles";
import useMediaQuery from "@mui/material/useMediaQuery";

interface DeviceSelectContainerProps {
  children: React.ReactNode;
}
const DeviceSelectContainer: React.VFC<DeviceSelectContainerProps> = (
  props
) => {
  const theme = useTheme();
  const isSmallViewport = useMediaQuery(theme.breakpoints.down("sm"));

  return (
    <Stack direction={isSmallViewport ? "column" : "row"} spacing={2}>
      {props.children}
    </Stack>
  );
};

export default DeviceSelectContainer;
