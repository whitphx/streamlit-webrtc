from aiortc.contrib.media import MediaRelay

from .eventloop import get_server_event_loop, loop_context
from .server import VER_GTE_1_14_0, get_current_server

_SERVER_GLOBAL_RELAY_ATTR_NAME_ = "streamlit-webrtc-global-relay"


def get_global_relay() -> MediaRelay:
    if VER_GTE_1_14_0:
        from streamlit.runtime.runtime import Runtime

        singleton = Runtime.instance()
    else:
        singleton = get_current_server()

    if hasattr(singleton, _SERVER_GLOBAL_RELAY_ATTR_NAME_):
        return getattr(singleton, _SERVER_GLOBAL_RELAY_ATTR_NAME_)
    else:
        loop = get_server_event_loop()
        with loop_context(loop):
            relay = MediaRelay()
            setattr(singleton, _SERVER_GLOBAL_RELAY_ATTR_NAME_, relay)
        return relay
