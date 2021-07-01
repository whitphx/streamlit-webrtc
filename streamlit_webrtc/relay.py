import asyncio
from typing import Dict

from aiortc.contrib.media import MediaRelay

from .eventloop import loop_context

_relays: Dict[asyncio.AbstractEventLoop, MediaRelay] = dict()


def get_relay(loop: asyncio.AbstractEventLoop) -> MediaRelay:
    global _relays

    if loop not in _relays:
        with loop_context(loop):
            relay = MediaRelay()
            _relays[loop] = relay

    return _relays[loop]
