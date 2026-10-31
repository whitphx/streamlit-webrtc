import fractions
import logging
import weakref
from typing import Any, Optional, Tuple

from aiortc import RTCRtpSender
from aiortc.codecs.opus import OpusEncoder
from aiortc.mediastreams import convert_timebase

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# Per sender: its RTP task, and the task's random timestamp origin and clock rate.
_origins: "weakref.WeakKeyDictionary[RTCRtpSender, Tuple[object, int, int]]" = (
    weakref.WeakKeyDictionary()
)

_MISSING = object()
_warned = False


def _warn_unreadable(sender: RTCRtpSender) -> None:
    global _warned
    if _warned:
        return
    _warned = True
    logger.warning(
        "Cannot read the RTP timestamp origin of %s, so rtp_timestamp() "
        "returns None. The installed aiortc may have changed its internals.",
        sender,
    )


def _origin_and_clock_rate(sender: RTCRtpSender) -> Optional[Tuple[int, int]]:
    # aiortc keeps no attribute for the random offset it adds to every RTP
    # timestamp: it is a local of the sender's RTP coroutine, read here from
    # the suspended coroutine's frame. See `_run_rtp()` in
    # https://github.com/aiortc/aiortc/blob/1.15.0/src/aiortc/rtcrtpsender.py#L357-L375
    task: Any = getattr(sender, "_RTCRtpSender__rtp_task", _MISSING)
    if task is _MISSING:
        _warn_unreadable(sender)
        return None
    if task is None or task.done():
        return None
    cached = _origins.get(sender)
    if cached is not None and cached[0] is task:
        return cached[1], cached[2]
    frame = getattr(task.get_coro(), "cr_frame", None)
    if frame is None:
        return None
    origin = frame.f_locals.get("timestamp_origin")
    clock_rate = getattr(frame.f_locals.get("codec"), "clockRate", None)
    # Both are set before the coroutine first yields, so a running task
    # without them is not the coroutine this module knows.
    if not isinstance(origin, int) or not isinstance(clock_rate, int):
        _warn_unreadable(sender)
        return None
    _origins[sender] = (task, origin, clock_rate)
    return origin, clock_rate


def outbound_rtp_timestamp(
    sender: RTCRtpSender, pts: int, time_base: fractions.Fraction
) -> Optional[int]:
    """The RTP timestamp under which the receiver plays the media that the
    track ``sender`` sends had at ``pts``.

    Returns ``None`` until the sender has started encoding, and when the
    installed aiortc does not let this module read the timestamp origin.
    """
    state = _origin_and_clock_rate(sender)
    if state is None:
        return None
    origin, clock_rate = state
    encoder = getattr(sender, "_RTCRtpSender__encoder", _MISSING)
    if encoder is _MISSING:
        _warn_unreadable(sender)
        return None
    if encoder is None:
        return None
    if isinstance(encoder, OpusEncoder):
        # aiortc's Opus encoder numbers packets from its first packet's pts,
        # which libopus puts one encoder lookahead before the first input
        # sample. The decoder delays its output by the same lookahead,
        # so subtracting that pts lands on the sample where the input at `pts`
        # is heard. See `OpusEncoder.encode()` in
        # https://github.com/aiortc/aiortc/blob/1.15.0/src/aiortc/codecs/opus.py#L51-L73
        if encoder.first_packet_pts is None:
            return None
        offset = round(pts * time_base * clock_rate) - encoder.first_packet_pts
    else:
        # The other encoders stamp a frame with its own pts in the codec's
        # clock, as `Vp8Encoder.encode()` does in
        # https://github.com/aiortc/aiortc/blob/1.15.0/src/aiortc/codecs/vpx.py#L245
        offset = convert_timebase(pts, time_base, fractions.Fraction(1, clock_rate))
    return (origin + offset) & 0xFFFFFFFF
