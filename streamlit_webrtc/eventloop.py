import asyncio
import contextlib
from typing import Union

from streamlit.server.server import Server


def get_server_event_loop() -> asyncio.AbstractEventLoop:
    current_server = Server.get_current()
    return current_server._ioloop.asyncio_loop


@contextlib.contextmanager
def loop_context(loop: asyncio.AbstractEventLoop):
    cur_ev_loop: Union[asyncio.AbstractEventLoop, None]
    try:
        cur_ev_loop = asyncio.get_event_loop()
    except RuntimeError:
        cur_ev_loop = None
    asyncio.set_event_loop(loop)

    yield

    asyncio.set_event_loop(cur_ev_loop)
