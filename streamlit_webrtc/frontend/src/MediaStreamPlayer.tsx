import { Streamlit } from "streamlit-component-lib";
import React, { useEffect, useCallback } from "react";

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

  return hasVideo ? (
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
  );
};

export default React.memo(MediaStreamPlayer);
