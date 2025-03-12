import React from "react";
import Paper from "@mui/material/Paper";
import VideocamOffIcon from "@mui/icons-material/VideocamOff";
import { styled } from "@mui/material/styles";

const StyledPaper = styled(Paper)({
  display: "flex",
  justifyContent: "center",
  alignItems: "center",
  width: "100%",
  height: "100%",
});

function VoidVideoPreview() {
  return (
    <StyledPaper>
      <VideocamOffIcon fontSize="large" />
    </StyledPaper>
  );
}

export default React.memo(VoidVideoPreview);
