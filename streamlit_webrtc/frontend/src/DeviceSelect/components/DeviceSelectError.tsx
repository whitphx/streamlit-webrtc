import React from "react";
import Paper from "@mui/material/Paper";
import Typography from "@mui/material/Typography";
import { styled } from "@mui/material/styles";

const StyledPaper = styled(Paper)(({ theme }) => ({
  display: "flex",
  justifyContent: "center",
  alignItems: "center",
  width: "100%",
  height: "100%",
  padding: theme.spacing(2),
  boxSizing: "border-box",
}));

interface DeviceSelectErrorProps {
  children: React.ReactNode;
}
const DeviceSelectError: React.VFC<DeviceSelectErrorProps> = (props) => {
  return (
    <StyledPaper>
      <Typography variant="h6" component="p">
        {props.children}
      </Typography>
    </StyledPaper>
  );
};

export default DeviceSelectError;
