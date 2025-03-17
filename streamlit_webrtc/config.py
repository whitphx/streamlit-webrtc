from typing import Dict, List, Optional, TypedDict, Union

RTCIceServer = TypedDict(
    "RTCIceServer",
    {
        "urls": Union[str, List[str]],
        "username": Optional[str],
        "credential": Optional[str],
    },
    total=False,
)


class RTCConfiguration(TypedDict, total=False):
    iceServers: Optional[List[RTCIceServer]]


Number = Union[int, float]


class DoubleRange(TypedDict, total=False):
    max: Number
    min: Number


class ConstrainDoubleRange(DoubleRange, total=False):
    exact: Number
    ideal: Number


class ConstrainBooleanParameters(TypedDict, total=False):
    exact: bool
    ideal: bool


class ULongRange(TypedDict, total=False):
    max: Number
    min: Number


class ConstrainULongRange(ULongRange, total=False):
    exact: Number
    ideal: Number


class ConstrainDOMStringParameters(TypedDict, total=False):
    exact: Union[str, List[str]]
    ideal: Union[str, List[str]]


ConstrainDouble = Union[Number, ConstrainDoubleRange]
ConstrainBoolean = Union[bool, ConstrainBooleanParameters]
ConstrainULong = Union[Number, ConstrainULongRange]
ConstrainDOMString = Union[str, List[str], ConstrainDOMStringParameters]


class MediaTrackConstraintSet(TypedDict, total=False):
    aspectRatio: ConstrainDouble
    autoGainControl: ConstrainBoolean
    channelCount: ConstrainULong
    # deviceId: ConstrainDOMString
    echoCancellation: ConstrainBoolean
    facingMode: ConstrainDOMString
    frameRate: ConstrainDouble
    groupId: ConstrainDOMString
    height: ConstrainULong
    latency: ConstrainDouble
    noiseSuppression: ConstrainBoolean
    resizeMode: ConstrainDOMString
    sampleRate: ConstrainULong
    sampleSize: ConstrainULong
    width: ConstrainULong


class MediaTrackConstraints(MediaTrackConstraintSet, total=False):
    advanced: List[MediaTrackConstraintSet]


# Ref: https://github.com/microsoft/TypeScript/blob/971133d5d0a56cf362571d21ac971888f8a66820/lib/lib.dom.d.ts#L719  # noqa
class MediaStreamConstraints(TypedDict, total=False):
    audio: Union[bool, MediaTrackConstraints]
    video: Union[bool, MediaTrackConstraints]
    peerIdentity: str


CSSProperties = Dict[str, Union[str, int, float]]


# Ref: https://github.com/DefinitelyTyped/DefinitelyTyped/blob/2563cecd0398fd9337b2806059446fb9d29abec2/types/react/index.d.ts#L1815 # noqa: E501
class HTMLAttributes(TypedDict, total=False):
    # Only necessary attributes are defined here
    hidden: bool
    style: CSSProperties


# Ref: https://github.com/DefinitelyTyped/DefinitelyTyped/blob/2563cecd0398fd9337b2806059446fb9d29abec2/types/react/index.d.ts#L2235 # noqa: E501
class MediaHTMLAttributes(HTMLAttributes, total=False):
    autoPlay: bool
    controls: bool
    controlsList: str
    crossOrigin: str
    loop: bool
    mediaGroup: str
    muted: bool
    playsInline: bool
    preload: str
    # src: str  # src is controlled by streamlit-webrtc


# Ref: https://github.com/DefinitelyTyped/DefinitelyTyped/blob/2563cecd0398fd9337b2806059446fb9d29abec2/types/react/index.d.ts#L2421 # noqa: E501
class VideoHTMLAttributes(MediaHTMLAttributes, total=False):
    height: Union[Number, str]
    # playsInline: bool  # This field already exists in MediaHTMLAttributes and overwriting it when extending is not allowed though it is in the original TypeScript code. # noqa: E501
    poster: str
    width: Union[Number, str]
    disablePictureInPicture: bool
    disableRemotePlayback: bool


# Ref: https://github.com/DefinitelyTyped/DefinitelyTyped/blob/2563cecd0398fd9337b2806059446fb9d29abec2/types/react/index.d.ts#L2016 # noqa: E501
class AudioHTMLAttributes(MediaHTMLAttributes, total=False):
    pass


class Translations(TypedDict, total=False):
    start: str
    stop: str
    select_device: str
    media_api_not_available: str
    device_ask_permission: str
    device_not_available: str
    device_access_denied: str


DEFAULT_MEDIA_STREAM_CONSTRAINTS = MediaStreamConstraints(audio=True, video=True)
DEFAULT_VIDEO_HTML_ATTRS = VideoHTMLAttributes(
    autoPlay=True, controls=True, style={"width": "100%"}
)
DEFAULT_AUDIO_HTML_ATTRS = AudioHTMLAttributes(autoPlay=True, controls=True)
