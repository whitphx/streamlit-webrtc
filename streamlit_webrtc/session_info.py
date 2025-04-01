from typing import Optional

from ._compat import (
    VER_GTE_1_12_1,
    VER_GTE_1_14_0,
    VER_GTE_1_18_0,
    SessionInfo,
    get_script_run_ctx,
)
from .server import get_current_server

# Ref: https://gist.github.com/tvst/036da038ab3e999a64497f42de966a92


class NoSessionError(Exception):
    pass


def get_session_id() -> str:
    ctx = get_script_run_ctx()
    if ctx is None:
        raise NoSessionError("Failed to get the thread context")

    return ctx.session_id


def get_this_session_info() -> Optional[SessionInfo]:
    # The original implementation of SessionState (https://gist.github.com/tvst/036da038ab3e999a64497f42de966a92) has a problem    # noqa: E501
    # as referred to in https://gist.github.com/tvst/036da038ab3e999a64497f42de966a92#gistcomment-3484515,                         # noqa: E501
    # then fixed here.
    # This code only works with streamlit>=0.65, https://gist.github.com/tvst/036da038ab3e999a64497f42de966a92#gistcomment-3418729 # noqa: E501
    session_id = get_session_id()

    if VER_GTE_1_18_0:
        from streamlit.runtime.runtime import Runtime

        return Runtime.instance()._session_mgr.get_session_info(session_id)  # type: ignore
    elif VER_GTE_1_14_0:
        from streamlit.runtime.runtime import Runtime

        return Runtime.instance()._get_session_info(session_id)  # type: ignore

    current_server = get_current_server()

    if VER_GTE_1_12_1:
        session_info = current_server._runtime._get_session_info(session_id)
    else:
        # streamlit < 1.12.1
        session_info = current_server._get_session_info(session_id)

    return session_info


def get_script_run_count(session_info: SessionInfo) -> int:
    """\
        Returns `session_info.script_run_count` or `session_info.report_run_count`
        according to the Streamlit version.
        See https://github.com/whitphx/streamlit-webrtc/issues/709
    """
    script_run_count = getattr(session_info, "script_run_count", None)
    if script_run_count is None:
        # For streamlit<1.6.0
        script_run_count = getattr(session_info, "report_run_count", None)

    if not isinstance(script_run_count, int):
        raise ValueError(
            f"script_run_count is unexpectedly not integer: {str(script_run_count)}"
        )

    return script_run_count
