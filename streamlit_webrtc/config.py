from typing import List, Optional, TypedDict, Union


class RTCIceServer(TypedDict):
    urls: Union[str, List[str]]
    username: Optional[str]
    credential: Optional[str]


class RTCConfiguration(TypedDict):
    iceServers: List[RTCIceServer]


class MediaStreamConstraints(TypedDict):
    audio: bool  # TODO: Support MediaTrackConstraints
    video: bool  # TODO: Support MediaTrackConstraints
