import asyncio
import logging
from typing import Callable, Dict, List, Mapping, Optional, TypedDict, Union

from aiortc import RTCDataChannel, RTCPeerConnection

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


DataChannelMessage = Union[str, bytes]


# Ref: https://w3c.github.io/webrtc-pc/#dom-rtcdatachannelinit
class DataChannelOptions(TypedDict, total=False):
    ordered: bool
    maxPacketLifeTime: int
    maxRetransmits: int
    protocol: str


_DATA_CHANNEL_OPTION_KEYS = frozenset(DataChannelOptions.__annotations__)


class DataChannelSpec(DataChannelOptions):
    label: str
    id: int


def compile_data_channel_specs(
    data_channels: Mapping[str, DataChannelOptions],
) -> List[DataChannelSpec]:
    specs: List[DataChannelSpec] = []
    # Both peers create every channel with `negotiated: true` and the same
    # stream ID, so the server already holds the channel object when the
    # connection opens. With in-band (DCEP) channels the server would only
    # learn about each channel from a `datachannel` event racing the first
    # message, and would have no handle to send on until then.
    for channel_id, (label, options) in enumerate(data_channels.items()):
        unknown_keys = set(options) - _DATA_CHANNEL_OPTION_KEYS
        if unknown_keys:
            raise ValueError(
                f"Unknown options for data channel {label!r}: "
                f"{', '.join(sorted(unknown_keys))}"
            )
        if (
            options.get("maxPacketLifeTime") is not None
            and options.get("maxRetransmits") is not None
        ):
            raise ValueError(
                f"Data channel {label!r} cannot set both "
                "maxPacketLifeTime and maxRetransmits"
            )
        spec = DataChannelSpec(label=label, id=channel_id)
        spec.update(options)
        specs.append(spec)
    return specs


class DataChannel:
    """Server-side handle on one data channel of a WebRTC session.

    All methods and properties can be used from any thread.
    """

    def __init__(self, channel: RTCDataChannel, loop: asyncio.AbstractEventLoop):
        self._channel = channel
        self._loop = loop

    @property
    def label(self) -> str:
        return self._channel.label

    @property
    def ready_state(self) -> str:
        """``"connecting"``, ``"open"``, ``"closing"``, or ``"closed"``."""
        return self._channel.readyState

    @property
    def buffered_amount(self) -> int:
        """Bytes queued for sending but not yet handed to the network.

        ``send(data, max_buffered=...)`` checks it to skip messages a slow
        link can't keep up with, instead of letting the queue (and the
        latency) grow.
        """
        return self._channel.bufferedAmount

    def send(
        self,
        data: Union[str, bytes, bytearray, memoryview],
        max_buffered: Optional[int] = None,
    ) -> bool:
        """Send ``data`` to the browser.

        A ``str`` arrives as a string message and anything bytes-like as a
        binary ``ArrayBuffer``.

        Returns ``True`` when the message was queued for sending, and
        ``False`` when it was not sent because the channel is not open or
        because more than ``max_buffered`` bytes are already waiting in
        ``buffered_amount``.
        """
        if self._channel.readyState != "open":
            return False
        if max_buffered is not None and self._channel.bufferedAmount > max_buffered:
            return False
        if not isinstance(data, (str, bytes)):
            # Copy now: the send happens later on the event loop thread,
            # and the caller may reuse the buffer in the meantime.
            data = bytes(data)
        try:
            self._loop.call_soon_threadsafe(self._send, data)
        except RuntimeError:
            return False
        return True

    def _send(self, data: DataChannelMessage) -> None:
        # The channel can close between the check in `send()`
        # and this call on the event loop thread.
        if self._channel.readyState != "open":
            logger.debug(
                "Data channel %s closed before a queued message was sent.",
                self.label,
            )
            return
        self._channel.send(data)


DataChannelMessageCallback = Callable[[DataChannel, DataChannelMessage], None]


def create_data_channels(
    pc: RTCPeerConnection,
    specs: List[DataChannelSpec],
    loop: asyncio.AbstractEventLoop,
    get_message_callback: Callable[[], Optional[DataChannelMessageCallback]],
) -> Dict[str, DataChannel]:
    channels: Dict[str, DataChannel] = {}
    for spec in specs:
        raw_channel = pc.createDataChannel(
            spec["label"],
            maxPacketLifeTime=spec.get("maxPacketLifeTime"),
            maxRetransmits=spec.get("maxRetransmits"),
            ordered=spec.get("ordered", True),
            protocol=spec.get("protocol", ""),
            negotiated=True,
            id=spec["id"],
        )
        channel = DataChannel(raw_channel, loop)

        def on_message(message: DataChannelMessage, channel=channel) -> None:
            # Looked up per message so a callback replaced on a rerun takes
            # effect without reconnecting.
            callback = get_message_callback()
            if callback is None:
                return
            try:
                callback(channel, message)
            except Exception:
                logger.exception(
                    "Error in the data channel message callback (%s)", channel.label
                )

        raw_channel.on("message", on_message)
        channels[spec["label"]] = channel
    return channels
