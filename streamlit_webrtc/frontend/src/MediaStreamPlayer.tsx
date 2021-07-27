import { Streamlit } from "streamlit-component-lib";
import React, {
  useEffect,
  useCallback,
  VideoHTMLAttributes,
  AudioHTMLAttributes,
  HTMLAttributes,
} from "react";

type UserDefinedHTMLVideoAttributes = Partial<
  Omit<
    VideoHTMLAttributes<HTMLVideoElement>,
    keyof Omit<HTMLAttributes<HTMLVideoElement>, "hidden" | "style"> | "src"
  >
>;
type UserDefinedHTMLAudioAttributes = Partial<
  Omit<
    AudioHTMLAttributes<HTMLVideoElement>,
    keyof Omit<HTMLAttributes<HTMLVideoElement>, "hidden" | "style"> | "src"
  >
>;

interface MediaStreamPlayerProps {
  stream: MediaStream;
  userDefinedVideoAttrs: UserDefinedHTMLVideoAttributes | undefined;
  userDefinedAudioAttrs: UserDefinedHTMLAudioAttributes | undefined;
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

  if (hasVideo) {
    // NOTE: Enumerate all allowed props instead of simply using spread operator
    //       passing all the fields in props.userDefinedVideoAttrs
    //       in order to block unexpected fields especially like dangerouslySetInnerHTML.
    const videoProps: VideoHTMLAttributes<HTMLVideoElement> = {
      hidden: props.userDefinedVideoAttrs?.hidden,
      style: props.userDefinedVideoAttrs?.style,
      autoPlay: props.userDefinedVideoAttrs?.autoPlay,
      controls: props.userDefinedVideoAttrs?.controls,
      controlsList: props.userDefinedVideoAttrs?.controlsList,
      crossOrigin: props.userDefinedVideoAttrs?.crossOrigin,
      loop: props.userDefinedVideoAttrs?.loop,
      mediaGroup: props.userDefinedVideoAttrs?.mediaGroup,
      muted: props.userDefinedVideoAttrs?.muted,
      playsInline: props.userDefinedVideoAttrs?.playsInline,
      preload: props.userDefinedVideoAttrs?.preload,
      height: props.userDefinedVideoAttrs?.height,
      poster: props.userDefinedVideoAttrs?.poster,
      width: props.userDefinedVideoAttrs?.width,
      disablePictureInPicture:
        props.userDefinedVideoAttrs?.disablePictureInPicture,
      disableRemotePlayback: props.userDefinedVideoAttrs?.disableRemotePlayback,
    };

    return (
      <video {...videoProps} ref={refCallback} onCanPlay={refreshFrameHeight} />
    );
  } else {
    const audioProps: AudioHTMLAttributes<HTMLAudioElement> = {
      hidden: props.userDefinedAudioAttrs?.hidden,
      style: props.userDefinedAudioAttrs?.style,
      autoPlay: props.userDefinedAudioAttrs?.autoPlay,
      controls: props.userDefinedAudioAttrs?.controls,
      controlsList: props.userDefinedAudioAttrs?.controlsList,
      crossOrigin: props.userDefinedAudioAttrs?.crossOrigin,
      loop: props.userDefinedAudioAttrs?.loop,
      mediaGroup: props.userDefinedAudioAttrs?.mediaGroup,
      muted: props.userDefinedAudioAttrs?.muted,
      playsInline: props.userDefinedAudioAttrs?.playsInline,
      preload: props.userDefinedAudioAttrs?.preload,
    };
    return <audio ref={refCallback} {...audioProps} />;
  }
};

export default React.memo(MediaStreamPlayer);
