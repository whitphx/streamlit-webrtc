import asyncio
from typing import Dict, Union

from aiortc.contrib.media import MediaRelay

_relays: Dict[asyncio.AbstractEventLoop, MediaRelay] = dict()


def get_relay(loop: asyncio.AbstractEventLoop) -> MediaRelay:
    global _relays

    if loop not in _relays:
        cur_ev_loop: Union[asyncio.AbstractEventLoop, None]
        try:
            cur_ev_loop = asyncio.get_event_loop()
        except RuntimeError:
            cur_ev_loop = None
        asyncio.set_event_loop(loop)

        relay = MediaRelay()
        _relays[loop] = relay

        asyncio.set_event_loop(cur_ev_loop)

    return _relays[loop]
