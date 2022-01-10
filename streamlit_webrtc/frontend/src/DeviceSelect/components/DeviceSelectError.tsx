import React from "react";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { styled } from "@mui/material/styles";

const StyledBox = styled(Box)({
  display: "flex",
  justifyContent: "center",
  alignItems: "center",
  width: "100%",
  height: "100%",
});

interface DeviceSelectErrorProps {
  children: React.ReactNode;
}
const DeviceSelectError: React.VFC<DeviceSelectErrorProps> = (props) => {
  return (
    <StyledBox>
      <Typography variant="h6" component="p">
        {props.children}
      </Typography>
    </StyledBox>
  );
};

export default DeviceSelectError;
