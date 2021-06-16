from typing import List, Optional, Union

try:
    from typing import TypedDict
except ImportError:
    from typing_extensions import TypedDict

RTCIceServer = TypedDict(
    "RTCIceServer",
    {
        "urls": Union[str, List[str]],
        "username": Optional[str],
        "credential": Optional[str],
    },
    total=False,
)


class RTCConfiguration(TypedDict):
    iceServers: List[RTCIceServer]


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
    deviceId: ConstrainDOMString
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
