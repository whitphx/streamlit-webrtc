import { Streamlit } from "streamlit-component-lib";
import React, { useCallback } from "react";
import Box from "@material-ui/core/Box";

interface MediaStreamPlayerProps {
  stream: MediaStream;
}
const MediaStreamPlayer: React.VFC<MediaStreamPlayerProps> = (props) => {
  const hasVideo = props.stream.getVideoTracks().length > 0;

  const refCallback = useCallback(
    (node: HTMLVideoElement | HTMLAudioElement | null) => {
      if (node) {
        node.srcObject = props.stream;
      }
    },
    [props.stream]
  );

  return (
    <Box>
      {hasVideo ? (
        <video
          style={{
            width: "100%",
          }}
          ref={refCallback}
          autoPlay
          controls
          onCanPlay={() => Streamlit.setFrameHeight()}
        />
      ) : (
        <audio ref={refCallback} autoPlay controls />
      )}
    </Box>
  );
};

export default React.memo(MediaStreamPlayer);
