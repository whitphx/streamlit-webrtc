"""Centralized re-exports of internal Streamlit symbols this package depends on.

The names below are not part of Streamlit's public API; importing them here keeps
the rest of the codebase decoupled from Streamlit's internal module layout. If a
future Streamlit release moves any of these, the only place that needs updating
is this file (and version-conditional fallbacks belong here, not at call sites).

Minimum supported Streamlit is 1.51.0 (matches Streamlit's first version
requiring Python >=3.10), so all paths below assume that floor.
"""

from streamlit import cache_data, rerun
from streamlit.runtime.app_session import AppSession, AppSessionState
from streamlit.runtime.scriptrunner import get_script_run_ctx
from streamlit.runtime.session_manager import ActiveSessionInfo as SessionInfo

__all__ = [
    "AppSession",
    "AppSessionState",
    "SessionInfo",
    "cache_data",
    "get_script_run_ctx",
    "rerun",
]
