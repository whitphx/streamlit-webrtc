import React, { useEffect, useState } from "react";
import Box from "@mui/material/Box";
import { styled } from "@mui/material/styles";

interface OverlayBoxProps {
  $transparent: boolean;
}
const OverlayBox = styled(Box, {
  shouldForwardProp: (prop) => prop !== "$transparent", // Prevent the custom prop to be passed to the inner HTML tag.
})<OverlayBoxProps>(({ theme, $transparent }) => ({
  margin: 0,
  padding: 0,
  position: "relative",
  "&:before": {
    position: "absolute",
    content: '""',
    width: "100%",
    height: "100%",
    opacity: $transparent ? 0 : 1,
    backgroundColor: theme.palette.background.default,
    transition: "opacity 0.3s",
  },
}));

interface DeferProps {
  time: number;
  children: React.ReactElement;
}
const Defer: React.VFC<DeferProps> = (props) => {
  const [elapsed, setElapsed] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      setElapsed(true);
    }, props.time);

    return () => clearTimeout(timer);
  }, [props.time]);

  return <OverlayBox $transparent={elapsed}>{props.children}</OverlayBox>;
};

export default Defer;
