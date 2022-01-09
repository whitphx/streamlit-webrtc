import React, { useEffect, useRef } from "react";

export interface VideoPreviewProps {
  deviceId: MediaDeviceInfo["deviceId"];
}
const VideoPreview: React.VFC<VideoPreviewProps> = (props) => {
  const videoRef = useRef<HTMLVideoElement>();

  useEffect(() => {
    if (props.deviceId == null) {
      return;
    }

    let stream: MediaStream | null = null;
    navigator.mediaDevices
      .getUserMedia({ video: { deviceId: props.deviceId }, audio: false })
      .then((_stream) => {
        stream = _stream;

        videoRef.current.srcObject = stream;
      });

    return () => {
      if (stream) {
        stream.getVideoTracks().forEach((track) => track.stop());
        stream.getAudioTracks().forEach((track) => track.stop());
      }
    };
  }, [props.deviceId]);

  if (props.deviceId == null) {
    return <p>No device selected</p>;
  }

  return <video ref={videoRef} autoPlay muted />;
};

export default React.memo(VideoPreview);
