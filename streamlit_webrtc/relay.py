from aiortc.contrib.media import MediaRelay
from streamlit.server.server import Server

from .eventloop import get_server_event_loop, loop_context

_SERVER_GLOBAL_RELAY_ATTR_NAME_ = "streamlit-webrtc-global-relay"

_server = Server.get_current()


def get_global_relay() -> MediaRelay:
    if hasattr(_server, _SERVER_GLOBAL_RELAY_ATTR_NAME_):
        return getattr(_server, _SERVER_GLOBAL_RELAY_ATTR_NAME_)
    else:
        loop = get_server_event_loop()
        with loop_context(loop):
            relay = MediaRelay()
            setattr(_server, _SERVER_GLOBAL_RELAY_ATTR_NAME_, relay)
        return relay
