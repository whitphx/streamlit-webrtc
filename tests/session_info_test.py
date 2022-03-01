from unittest.mock import Mock

from streamlit.server.server import SessionInfo

from streamlit_webrtc.session_info import get_script_run_count


def test_get_script_run_count():
    session_info = SessionInfo(ws=Mock(), session=Mock())
    assert get_script_run_count(session_info) == 0
