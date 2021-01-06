import os
import json
import logging
from typing import Dict, Hashable, Optional, Union
import streamlit.components.v1 as components

from webrtc import WebRtcWorker
import SessionState


_RELEASE = False

if not _RELEASE:
    _component_func = components.declare_component(
        "my_component",
        url="http://localhost:3001",
    )
else:
    parent_dir = os.path.dirname(os.path.abspath(__file__))
    build_dir = os.path.join(parent_dir, "frontend/build")
    _component_func = components.declare_component("my_component", path=build_dir)


session_state = SessionState.get(webrtc_workers={})


def get_webrtc_worker(key: Hashable) -> Union[WebRtcWorker, None]:
    return session_state.webrtc_workers.get(key)


def set_webrtc_worker(key: Hashable, webrtc_worker: WebRtcWorker) -> None:
    session_state.webrtc_workers[key] = webrtc_worker


def unset_webrtc_worker(key: Hashable) -> None:
    del session_state.webrtc_workers[key]


def my_component(key: Optional[str] = None):
    webrtc_worker = get_webrtc_worker(key)

    sdp_answer_json = None
    if webrtc_worker:
        sdp_answer_json = json.dumps(
            {
                "sdp": webrtc_worker.pc.localDescription.sdp,
                "type": webrtc_worker.pc.localDescription.type,
            }
        )

    component_value: Union[Dict, None] = _component_func(
        key=key, sdp_answer_json=sdp_answer_json
    )

    if component_value:
        playing = component_value.get("playing", False)
        sdp_offer_json = component_value.get("sdpOfferJson")

        if webrtc_worker:
            if not playing:
                webrtc_worker.stop()
                unset_webrtc_worker(key)
        else:
            if sdp_offer_json:
                sdp_offer = json.loads(sdp_offer_json)
                st.write("SDP offer:", sdp_offer)

                webrtc_worker = WebRtcWorker()
                localDescription = webrtc_worker.process_offer(
                    sdp_offer["sdp"], sdp_offer["type"]
                )
                set_webrtc_worker(key, webrtc_worker)
                st.experimental_rerun()

    return component_value


# Add some test code to play with the component while it's in development.
# During development, we can run this just as we would any other Streamlit
# app: `$ streamlit run my_component/__init__.py`
if not _RELEASE:
    import streamlit as st

    logging.basicConfig()

    st.subheader("WebRTC component")

    my_component(key="foo")
