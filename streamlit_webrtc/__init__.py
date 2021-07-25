"""streamlit-webrtc
"""

try:
    import importlib.metadata as importlib_metadata
except ModuleNotFoundError:
    # Python < 3.8
    import importlib_metadata  # type: ignore

from .component import (
    ClientSettings,
    WebRtcStreamerContext,
    WebRtcStreamerState,
    webrtc_streamer,
)
from .config import (
    AudioHTMLAttributes,
    MediaStreamConstraints,
    RTCConfiguration,
    VideoHTMLAttributes,
)
from .factory import create_mix_track, create_process_track
from .mix import MixerBase
from .webrtc import (
    AudioProcessorBase,
    AudioProcessorFactory,
    AudioReceiver,
    MediaPlayerFactory,
    MediaRecorderFactory,
    VideoProcessorBase,
    VideoProcessorFactory,
    VideoReceiver,
    VideoTransformerBase,
    WebRtcMode,
    WebRtcWorker,
)

# Set __version__ dynamically base on metadata.
# https://github.com/python-poetry/poetry/issues/1036#issuecomment-489880822
# https://github.com/python-poetry/poetry/issues/144#issuecomment-623927302
# https://github.com/python-poetry/poetry/pull/2366#issuecomment-652418094
try:
    __version__ = importlib_metadata.version(__name__)
except importlib_metadata.PackageNotFoundError:
    pass

# For backward compatibility
VideoTransformerFactory = VideoProcessorFactory


__all__ = [
    "webrtc_streamer",
    "ClientSettings",
    "AudioProcessorBase",
    "AudioProcessorFactory",
    "AudioReceiver",
    "MediaPlayerFactory",
    "MediaRecorderFactory",
    "VideoProcessorBase",
    "VideoProcessorFactory",
    "VideoTransformerBase",  # XXX: Deprecated
    "VideoReceiver",
    "WebRtcMode",
    "WebRtcWorker",
    "MediaStreamConstraints",
    "RTCConfiguration",
    "VideoHTMLAttributes",
    "AudioHTMLAttributes",
    "create_process_track",
    "create_mix_track",
    "MixerBase",
    "WebRtcStreamerContext",
    "WebRtcStreamerState",
]
