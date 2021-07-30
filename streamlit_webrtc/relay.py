from aiortc.contrib.media import MediaRelay
from streamlit.server.server import Server

from .eventloop import get_server_event_loop, loop_context

_SERVER_GLOBAL_RELAY_ATTR_NAME_ = "streamlit-webrtc-global-relay"

# NOTE: Accessing the server object only when it is necessary (in `get_global_relay()`)
#       is important for this module to be compatible with multiprocessing because
#       in a forked process `Server.get_current()` always raises an error
#       as the Streamlit (actually Tornado) server does not exist in that process.
#       See https://github.com/whitphx/streamlit-webrtc/issues/354
_server = None


def get_global_relay() -> MediaRelay:
    global _server
    if _server is None:
        _server = Server.get_current()

    if hasattr(_server, _SERVER_GLOBAL_RELAY_ATTR_NAME_):
        return getattr(_server, _SERVER_GLOBAL_RELAY_ATTR_NAME_)
    else:
        loop = get_server_event_loop()
        with loop_context(loop):
            relay = MediaRelay()
            setattr(_server, _SERVER_GLOBAL_RELAY_ATTR_NAME_, relay)
        return relay
