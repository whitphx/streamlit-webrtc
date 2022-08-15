import logging

import streamlit as st
from packaging import version

logger = logging.getLogger(__name__)

_server = None

VERSION_1_12_0 = version.parse("1.12.0")


def _is_modern_architecture() -> bool:
    """Returns if the imported streamlit package version is >=1.12.0.
    It is because since that version, streamlit has changed its internal architecture
    making `web` and `runtime` submodules to which some files have been moved
    decoupling the web server-related files and the core runtime,
    e.g. https://github.com/streamlit/streamlit/pull/4956.

    During this a huge refactoring, `Server._singleton` and
    its accessor `Server.get_current()` have been removed
    (https://github.com/streamlit/streamlit/pull/4966)
    that we have been using as a server-wide global object,
    so we have to change the way to access it.
    """
    return version.parse(st.__version__) >= VERSION_1_12_0


def get_current_server():
    global _server
    if _server:
        return _server

    if _is_modern_architecture():
        logger.debug(
            "The running Streamlit version is gte 1.12.0. "
            "Try to get the server instance"
        )

        import gc

        from streamlit.web.server.server import Server

        servers = [obj for obj in gc.get_objects() if isinstance(obj, Server)]

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
