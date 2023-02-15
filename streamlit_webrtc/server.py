import logging

from ._compat import VER_GTE_1_12_0

logger = logging.getLogger(__name__)

_server = None


class NoServerError(Exception):
    pass


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
            raise NoServerError("Unexpectedly no server exists")
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
