import { Streamlit } from "streamlit-component-lib";
import Box from "@mui/material/Box";
import type { FrontendScriptMedia } from "./webrtc/frontend-script";
import React, {
  useEffect,
  useCallback,
  type MutableRefObject,
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

function pickVideoProps(
  attrs: UserDefinedHTMLVideoAttributes | undefined,
): VideoHTMLAttributes<HTMLVideoElement> {
  // NOTE: Enumerate all allowed props instead of simply using spread operator
  //       passing all the fields in attrs
  //       in order to block unexpected fields especially like dangerouslySetInnerHTML.
  return {
    hidden: attrs?.hidden,
    style: attrs?.style,
    autoPlay: attrs?.autoPlay,
    controls: attrs?.controls,
    controlsList: attrs?.controlsList,
    crossOrigin: attrs?.crossOrigin,
    loop: attrs?.loop,
    mediaGroup: attrs?.mediaGroup,
    muted: attrs?.muted,
    playsInline: attrs?.playsInline,
    preload: attrs?.preload,
    height: attrs?.height,
    poster: attrs?.poster,
    width: attrs?.width,
    disablePictureInPicture: attrs?.disablePictureInPicture,
    disableRemotePlayback: attrs?.disableRemotePlayback,
  };
}

function pickAudioProps(
  attrs: UserDefinedHTMLAudioAttributes | undefined,
): AudioHTMLAttributes<HTMLAudioElement> {
  return {
    hidden: attrs?.hidden,
    style: attrs?.style,
    autoPlay: attrs?.autoPlay,
    controls: attrs?.controls,
    controlsList: attrs?.controlsList,
    crossOrigin: attrs?.crossOrigin,
    loop: attrs?.loop,
    mediaGroup: attrs?.mediaGroup,
    muted: attrs?.muted,
    playsInline: attrs?.playsInline,
    preload: attrs?.preload,
  };
}

interface MediaStreamPlayerProps {
  stream: MediaStream;
  userDefinedVideoAttrs: UserDefinedHTMLVideoAttributes | undefined;
  userDefinedAudioAttrs: UserDefinedHTMLAudioAttributes | undefined;
}
function MediaStreamPlayer(props: MediaStreamPlayerProps) {
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
    [props.stream],
  );

  const refreshFrameHeight = useCallback(() => Streamlit.setFrameHeight(), []);

  if (hasVideo) {
    return (
      <video
        {...pickVideoProps(props.userDefinedVideoAttrs)}
        ref={refCallback}
        onCanPlay={refreshFrameHeight}
      />
    );
  } else {
    return (
      <audio
        ref={refCallback}
        {...pickAudioProps(props.userDefinedAudioAttrs)}
      />
    );
  }
}

export default React.memo(MediaStreamPlayer);

interface PersistentMediaStreamPlayerProps {
  stream: MediaStream | null;
  placeholder: React.ReactNode;
  mediaRef: MutableRefObject<FrontendScriptMedia>;
  userDefinedVideoAttrs: UserDefinedHTMLVideoAttributes | undefined;
  userDefinedAudioAttrs: UserDefinedHTMLAudioAttributes | undefined;
}
/**
 * Plays the stream like `MediaStreamPlayer`, but keeps one `<video>` and one
 * `<audio>` element mounted for as long as it is, whether a stream is playing
 * or not, so that `frontend_script` can be handed both before the stream
 * arrives and keep using them across the session.
 */
export function PersistentMediaStreamPlayer(
  props: PersistentMediaStreamPlayerProps,
) {
  const { stream, mediaRef } = props;
  useEffect(() => {
    Streamlit.setFrameHeight();
  });

  const hasVideo = stream != null && stream.getVideoTracks().length > 0;
  const hasAudioOnly = stream != null && !hasVideo;

  useEffect(() => {
    const { video, audio } = mediaRef.current;
    if (video) video.srcObject = hasVideo ? stream : null;
    if (audio) audio.srcObject = hasAudioOnly ? stream : null;
  }, [mediaRef, stream, hasVideo, hasAudioOnly]);

  const refreshFrameHeight = useCallback(() => Streamlit.setFrameHeight(), []);

  return (
    <>
      {stream == null && props.placeholder}
      {/* The wrappers hide whichever element is not playing, leaving the
          elements' own `hidden` and `style` to the app. */}
      <Box display={hasVideo ? "contents" : "none"}>
        <video
          {...pickVideoProps(props.userDefinedVideoAttrs)}
          ref={(node) => {
            mediaRef.current.video = node ?? undefined;
          }}
          onCanPlay={refreshFrameHeight}
        />
      </Box>
      <Box display={hasAudioOnly ? "contents" : "none"}>
        <audio
          {...pickAudioProps(props.userDefinedAudioAttrs)}
          ref={(node) => {
            mediaRef.current.audio = node ?? undefined;
          }}
        />
      </Box>
    </>
  );
}
