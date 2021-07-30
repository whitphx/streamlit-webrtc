from aiortc.contrib.media import MediaRelay
from streamlit.server.server import Server

from .eventloop import get_server_event_loop, loop_context

_SERVER_GLOBAL_RELAY_ATTR_NAME_ = "streamlit-webrtc-global-relay"


def get_global_relay() -> MediaRelay:
    server = Server.get_current()

    if hasattr(server, _SERVER_GLOBAL_RELAY_ATTR_NAME_):
        return getattr(server, _SERVER_GLOBAL_RELAY_ATTR_NAME_)
    else:
        loop = get_server_event_loop()
        with loop_context(loop):
            relay = MediaRelay()
            setattr(server, _SERVER_GLOBAL_RELAY_ATTR_NAME_, relay)
        return relay
