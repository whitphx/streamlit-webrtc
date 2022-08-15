from unittest.mock import Mock

from streamlit_webrtc.session_info import SessionInfo, get_script_run_count


def test_get_script_run_count():
    session_info = SessionInfo(client=Mock(), session=Mock())
    assert get_script_run_count(session_info) == 0
