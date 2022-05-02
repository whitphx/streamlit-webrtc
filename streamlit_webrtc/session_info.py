from typing import Optional

from streamlit.server.server import SessionInfo

try:
    from streamlit.scriptrunner import get_script_run_ctx
except ModuleNotFoundError:
    # streamlit < 1.8
    try:
        from streamlit.script_run_context import get_script_run_ctx  # type: ignore
    except ModuleNotFoundError:
        # streamlit < 1.4
        from streamlit.report_thread import (  # type: ignore
            get_report_ctx as get_script_run_ctx,
        )

from streamlit.server.server import Server

# Ref: https://gist.github.com/tvst/036da038ab3e999a64497f42de966a92


def get_session_id() -> str:
    ctx = get_script_run_ctx()
    if ctx is None:
        raise Exception("Failed to get the thread context")

    return ctx.session_id


def get_this_session_info() -> Optional[SessionInfo]:
    current_server = Server.get_current()

    # The original implementation of SessionState (https://gist.github.com/tvst/036da038ab3e999a64497f42de966a92) has a problem    # noqa: E501
    # as referred to in https://gist.github.com/tvst/036da038ab3e999a64497f42de966a92#gistcomment-3484515,                         # noqa: E501
    # then fixed here.
    # This code only works with streamlit>=0.65, https://gist.github.com/tvst/036da038ab3e999a64497f42de966a92#gistcomment-3418729 # noqa: E501
    session_id = get_session_id()
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
