import asyncio
import contextlib
from typing import Union

from tornado.platform.asyncio import BaseAsyncIOLoop

from ._compat import VER_GTE_1_12_0, VER_GTE_1_12_1, VER_GTE_1_14_0
from .server import get_current_server


def get_global_event_loop() -> asyncio.AbstractEventLoop:
    if VER_GTE_1_14_0:
        from streamlit.runtime.runtime import Runtime

        async_objs = Runtime.instance()._get_async_objs()  # type: ignore
        return async_objs.eventloop

    current_server = get_current_server()

    if VER_GTE_1_12_1:
        async_objs = current_server._runtime._get_async_objs()
        return async_objs.eventloop

    if VER_GTE_1_12_0:
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
