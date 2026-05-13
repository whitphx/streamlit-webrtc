from aiortc.contrib.media import MediaRelay
from streamlit.runtime.runtime import Runtime

from .eventloop import get_global_event_loop, loop_context

_SERVER_GLOBAL_RELAY_ATTR_NAME_ = "streamlit-webrtc-global-relay"


def get_global_relay() -> MediaRelay:
    singleton = Runtime.instance()  # type: ignore

    if hasattr(singleton, _SERVER_GLOBAL_RELAY_ATTR_NAME_):
        return getattr(singleton, _SERVER_GLOBAL_RELAY_ATTR_NAME_)
    else:
        loop = get_global_event_loop()
        with loop_context(loop):
            relay = MediaRelay()
            setattr(singleton, _SERVER_GLOBAL_RELAY_ATTR_NAME_, relay)
        return relay
