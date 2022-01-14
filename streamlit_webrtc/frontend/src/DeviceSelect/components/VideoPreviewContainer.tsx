import Box from "@mui/material/Box";
import { styled } from "@mui/material/styles";

const StyledBox = styled(Box)(({ theme }) => ({
  position: "relative",
  [theme.breakpoints.down("sm")]: {
    width: "100%",
  },
  width: theme.spacing(24),
  height: theme.spacing(16),
  maxHeight: theme.spacing(16),
  display: "flex",
  justifyContent: "center",
  alignItems: "center",
}));

const VideoPreviewContainer = StyledBox;

export default VideoPreviewContainer;
