"""streamlit-webrtc"""

import importlib.metadata

from .component import (
    WebRtcStreamerContext,
    WebRtcStreamerState,
    webrtc_streamer,
)
from .config import (
    DEFAULT_AUDIO_HTML_ATTRS,
    DEFAULT_MEDIA_STREAM_CONSTRAINTS,
    DEFAULT_VIDEO_HTML_ATTRS,
    AudioHTMLAttributes,
    MediaStreamConstraints,
    RTCConfiguration,
    Translations,
    VideoHTMLAttributes,
)
from .credentials import (
    get_hf_ice_servers,
    get_twilio_ice_servers,
)
from .factory import (
    create_audio_source_track,
    create_mix_track,
    create_process_track,
    create_video_source_track,
)
from .mix import MediaStreamMixTrack, MixerCallback
from .source import (
    AudioSourceCallback,
    AudioSourceTrack,
    VideoSourceCallback,
    VideoSourceTrack,
)
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
    __version__ = importlib.metadata.version(__name__)
except importlib.metadata.PackageNotFoundError:
    pass

# For backward compatibility
VideoTransformerFactory = VideoProcessorFactory


__all__ = [
    "webrtc_streamer",
    "AudioProcessorBase",
    "AudioProcessorFactory",
    "AudioReceiver",
    "MediaPlayerFactory",
    "MediaRecorderFactory",
    "VideoProcessorBase",
    "VideoProcessorFactory",
    "VideoTransformerBase",  # XXX: Deprecated
    "VideoReceiver",
    "VideoSourceTrack",
    "VideoSourceCallback",
    "AudioSourceTrack",
    "AudioSourceCallback",
    "create_video_source_track",
    "create_audio_source_track",
    "WebRtcMode",
    "WebRtcWorker",
    "MediaStreamConstraints",
    "RTCConfiguration",
    "Translations",
    "VideoHTMLAttributes",
    "AudioHTMLAttributes",
    "create_process_track",
    "create_mix_track",
    "MixerCallback",
    "MediaStreamMixTrack",
    "WebRtcStreamerContext",
    "WebRtcStreamerState",
    "DEFAULT_AUDIO_HTML_ATTRS",
    "DEFAULT_MEDIA_STREAM_CONSTRAINTS",
    "DEFAULT_VIDEO_HTML_ATTRS",
    "get_hf_ice_servers",
    "get_twilio_ice_servers",
]
