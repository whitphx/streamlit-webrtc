import React, { useEffect, useRef } from "react";
import VideoPreviewComponent from "./components/VideoPreview";
import { stopAllTracks } from "./utils";

export interface VideoPreviewProps {
  deviceId: MediaDeviceInfo["deviceId"];
}
function VideoPreview(props: VideoPreviewProps) {
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    if (props.deviceId == null) {
      return;
    }

    let stream: MediaStream | null = null;
    let unmounted = false;
    navigator.mediaDevices
      .getUserMedia({
        // `exact` so the preview shows the selected device, not a browser
        // fallback — a bare deviceId is only an "ideal" hint.
        video: { deviceId: { exact: props.deviceId } },
        audio: false,
      })
      .then((_stream) => {
        stream = _stream;

        if (unmounted) {
          stopAllTracks(stream);
          return;
        }

        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }
      });

    return () => {
      unmounted = true;
      if (stream) {
        stopAllTracks(stream);
      }
    };
  }, [props.deviceId]);

  return <VideoPreviewComponent ref={videoRef} autoPlay muted />;
}

export default React.memo(VideoPreview);
