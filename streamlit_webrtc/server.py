import logging

import streamlit as st
from packaging import version

logger = logging.getLogger(__name__)

_server = None

ST_VERSION = version.parse(st.__version__)

VERSION_1_12_0 = version.parse("1.12.0")
VERSION_1_12_1 = version.parse("1.12.1")

VER_GTE_1_12_0 = ST_VERSION >= VERSION_1_12_0
""" Since 1.12.0, Streamlit has changed its internal architecture
creating new `web` and `runtime` submodules to which some files have been moved
decoupling the web server-related files and the core runtime,
e.g. https://github.com/streamlit/streamlit/pull/4956.

During this a huge refactoring, `Server._singleton` and
its accessor `Server.get_current()` have been removed
(https://github.com/streamlit/streamlit/pull/4966)
that we have been using as a server-wide global object,
so we have to change the way to access it.
"""

VER_GTE_1_12_1 = ST_VERSION >= VERSION_1_12_1
""" Since 1.12.1, as a part of the decoupling of the runtime and the web server,
a large part of the `Server` class attributes including the session states
has moved to the `runtime` submodule.

Ref: https://github.com/streamlit/streamlit/pull/5136
"""


def get_current_server():
    global _server
    if _server:
        return _server

    if VER_GTE_1_12_0:
        logger.debug(
            "The running Streamlit version is gte 1.12.0. "
            "Try to get the server instance"
        )

        import gc

        from streamlit.web.server.server import Server

        def is_server(obj) -> bool:
            try:
                return isinstance(obj, Server)
            except ReferenceError:  # This is necessary due to https://github.com/whitphx/streamlit-webrtc/issues/1040  # noqa: E501
                return False

        servers = [obj for obj in gc.get_objects() if is_server(obj)]

        if len(servers) == 0:
            raise RuntimeError("Unexpectedly no server exists")
        if len(servers) > 1:
            logger.warning(
                "Unexpectedly multiple server instances exist. Use the first one."
            )

        _server = servers[0]
    else:
        logger.debug(
            "The running Streamlit version is less than 1.12.0. "
            "Call Server.get_current()"
        )
        try:
            from streamlit.web.server.server import Server
        except ModuleNotFoundError:
            # streamlit < 1.12.0
            from streamlit.server.server import Server

        _server = Server.get_current()

    return _server
