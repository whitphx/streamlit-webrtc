from unittest.mock import Mock

from streamlit_webrtc.server import VER_GTE_1_12_0
from streamlit_webrtc.session_info import SessionInfo, get_script_run_count


def test_get_script_run_count():
    if VER_GTE_1_12_0:
        session_info = SessionInfo(client=Mock(), session=Mock())
    else:
        session_info = SessionInfo(ws=Mock(), session=Mock())
    assert get_script_run_count(session_info) == 0
