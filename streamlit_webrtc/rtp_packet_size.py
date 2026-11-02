import logging
import os

from aiortc.codecs import h264, vpx

logger = logging.getLogger(__name__)

PAYLOAD_SIZE_ENV_VAR = "STREAMLIT_WEBRTC_MAX_VIDEO_RTP_PAYLOAD_SIZE"

# The fixed payload size of aiortc's VP8 and H.264 packetizers up to 1.14.0.
# Its RTP packets of about 1325 bytes are dropped by some TURN relay legs,
# VPNs and IPv6 tunnels, while the small audio packets get through.
AIORTC_LEGACY_PAYLOAD_SIZE = 1300

# Browsers keep video RTP packets within 1200 bytes, see
# https://webrtc.googlesource.com/src/+/8290a27b8d720439e99762bcfa9b51afc9a9d613/media/base/media_constants.h#25
# This leaves room for the RTP header, its extensions
# and the RTX original sequence number.
DEFAULT_PAYLOAD_SIZE = 1150


def cap_video_rtp_payload_size() -> None:
    value = os.environ.get(PAYLOAD_SIZE_ENV_VAR, "").strip()
    payload_size = DEFAULT_PAYLOAD_SIZE
    if value:
        try:
            payload_size = int(value)
        except ValueError:
            logger.warning(
                "Ignoring %s=%r, which is not an integer", PAYLOAD_SIZE_ENV_VAR, value
            )

    if payload_size <= 0:
        return

    for module in (vpx, h264):
        # Leave a value other than the legacy one alone: it is either an aiortc
        # default that already fits, or one the app has set itself.
        if getattr(module, "PACKET_MAX", None) == AIORTC_LEGACY_PAYLOAD_SIZE:
            logger.debug("Setting %s.PACKET_MAX to %d", module.__name__, payload_size)
            setattr(module, "PACKET_MAX", payload_size)
