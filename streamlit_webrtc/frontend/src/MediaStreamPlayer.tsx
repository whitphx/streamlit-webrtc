import { Streamlit } from "streamlit-component-lib";
import React, { useEffect, useCallback } from "react";

const videoStyle: JSX.IntrinsicElements["video"]["style"] = {
  width: "100%",
};

interface MediaStreamPlayerProps {
  stream: MediaStream;
}
const MediaStreamPlayer: React.VFC<MediaStreamPlayerProps> = (props) => {
  useEffect(() => {
    Streamlit.setFrameHeight();
  });

  const hasVideo = props.stream.getVideoTracks().length > 0;

  const refCallback = useCallback(
    (node: HTMLVideoElement | HTMLAudioElement | null) => {
      if (node) {
        node.srcObject = props.stream;
      }
    },
    [props.stream]
  );

  const refreshFrameHeight = useCallback(() => Streamlit.setFrameHeight(), []);

  return hasVideo ? (
    <video
      style={videoStyle}
      ref={refCallback}
      autoPlay
      controls
      onCanPlay={refreshFrameHeight}
    />
  ) : (
    <audio ref={refCallback} autoPlay controls />
  );
};

export default React.memo(MediaStreamPlayer);
