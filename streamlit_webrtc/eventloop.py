import asyncio
import contextlib
from typing import Union

from streamlit.runtime.runtime import Runtime


def get_global_event_loop() -> asyncio.AbstractEventLoop:
    async_objs = Runtime.instance()._get_async_objs()  # type: ignore
    return async_objs.eventloop


@contextlib.contextmanager
def loop_context(loop: asyncio.AbstractEventLoop):
    cur_ev_loop: Union[asyncio.AbstractEventLoop, None]
    try:
        # Try to get the running loop first (if we're in async context)
        cur_ev_loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop, try to get the current loop from policy
        try:
            cur_ev_loop = asyncio.get_event_loop_policy().get_event_loop()
        except RuntimeError:
            cur_ev_loop = None

    asyncio.set_event_loop(loop)

    yield

    asyncio.set_event_loop(cur_ev_loop)
