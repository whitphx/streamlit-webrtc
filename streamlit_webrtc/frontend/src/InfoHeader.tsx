import React, { useEffect } from "react";
import Alert from "@mui/material/Alert";
import Fade from "@mui/material/Fade";
import { Streamlit } from "streamlit-component-lib";

export interface InfoHeaderProps {
  error: Error | undefined | null;
  shouldShowTakingTooLongWarning: boolean;
}
function InfoHeader(props: InfoHeaderProps) {
  useEffect(() => {
    Streamlit.setFrameHeight();
  });

  return (
    <>
      {props.error ? (
        <Alert severity="error">
          {props.error.name}: {props.error.message}
        </Alert>
      ) : (
        props.shouldShowTakingTooLongWarning && (
          <Fade in={true} timeout={1000}>
            <Alert severity="warning">
              Connection is taking longer than expected. Check your network or ask the developer for STUN/TURN settings if the problem persists.
            </Alert>
          </Fade>
        )
      )}
    </>
  );
}

export default React.memo(InfoHeader);
