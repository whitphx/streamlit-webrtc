import React, { useEffect, useRef } from "react";

export interface VideoPreviewProps {
  deviceId: MediaDeviceInfo["deviceId"];
}
const VideoPreview: React.VFC<VideoPreviewProps> = (props) => {
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    if (props.deviceId == null) {
      return;
    }

    let stream: MediaStream | null = null;
    navigator.mediaDevices
      .getUserMedia({ video: { deviceId: props.deviceId }, audio: false })
      .then((_stream) => {
        stream = _stream;

        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }
      });

    return () => {
      if (stream) {
        stream.getVideoTracks().forEach((track) => track.stop());
        stream.getAudioTracks().forEach((track) => track.stop());
      }
    };
  }, [props.deviceId]);

  return <video ref={videoRef} autoPlay muted />;
};

export default React.memo(VideoPreview);
