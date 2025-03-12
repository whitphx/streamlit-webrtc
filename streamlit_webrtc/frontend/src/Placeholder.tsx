import { Streamlit } from "streamlit-component-lib";
import React, { useEffect } from "react";
import Paper from "@mui/material/Paper";
import CircularProgress from "@mui/material/CircularProgress";
import VideoLabelIcon from "@mui/icons-material/VideoLabel";
import { styled } from "@mui/material/styles";

const StyledPaper = styled(Paper)(({ theme }) => ({
  padding: theme.spacing(4),
  display: "flex",
  justifyContent: "center",
  alignItems: "center",
  width: "100%",
}));

interface PlaceholderProps {
  loading: boolean;
}
function Placeholder(props: PlaceholderProps) {
  useEffect(() => {
    Streamlit.setFrameHeight();
  });

  return (
    <StyledPaper elevation={0}>
      {props.loading ? (
        <CircularProgress />
      ) : (
        <VideoLabelIcon fontSize="large" />
      )}
    </StyledPaper>
  );
};

export default React.memo(Placeholder);
