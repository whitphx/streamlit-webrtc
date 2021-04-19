import { Streamlit } from "streamlit-component-lib";
import React from "react";
import Box from "@material-ui/core/Box";

interface MediaStreamPlayerProps {
  stream: MediaStream;
}
const MediaStreamPlayer: React.VFC<MediaStreamPlayerProps> = (props) => {
  return (
    <Box>
      {props.stream.getVideoTracks().length > 0 ? (
        <video
          style={{
            width: "100%",
          }}
          ref={(node) => {
            if (node) {
              node.srcObject = props.stream;
            }
          }}
          autoPlay
          controls
          onCanPlay={() => Streamlit.setFrameHeight()}
        />
      ) : (
        <audio
          ref={(node) => {
            if (node) {
              node.srcObject = props.stream;
            }
          }}
          autoPlay
          controls
        />
      )}
    </Box>
  );
};

export default React.memo(MediaStreamPlayer);
