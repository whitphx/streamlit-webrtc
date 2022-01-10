import React from "react";
import Paper from "@mui/material/Paper";
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
  return <StyledPaper>{props.children}</StyledPaper>;
};

export default DeviceSelectError;
