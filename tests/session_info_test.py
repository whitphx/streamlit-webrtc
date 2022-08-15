from unittest.mock import Mock

from streamlit_webrtc.server import _is_modern_architecture
from streamlit_webrtc.session_info import SessionInfo, get_script_run_count


def test_get_script_run_count():
    if _is_modern_architecture():
        session_info = SessionInfo(client=Mock(), session=Mock())
    else:
        session_info = SessionInfo(ws=Mock(), session=Mock())
    assert get_script_run_count(session_info) == 0
