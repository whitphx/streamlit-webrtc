import asyncio
import contextlib
from typing import Union

from tornado.platform.asyncio import BaseAsyncIOLoop

from .server import _is_modern_architecture, get_current_server


def get_server_event_loop() -> asyncio.AbstractEventLoop:
    current_server = get_current_server()

    if _is_modern_architecture():
        return current_server._eventloop

    ioloop = current_server._ioloop

    # `ioloop` is expected to be of type `BaseAsyncIOLoop`,
    # which has the `asyncio_loop` attribute.
    if not isinstance(ioloop, BaseAsyncIOLoop):
        raise Exception("Unexpectedly failed to access the asyncio event loop.")

    return ioloop.asyncio_loop


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
