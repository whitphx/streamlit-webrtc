from typing import Optional

from streamlit.runtime.runtime import Runtime

from ._compat import SessionInfo, get_script_run_ctx


class NoSessionError(Exception):
    pass


def get_session_id() -> str:
    ctx = get_script_run_ctx()
    if ctx is None:
        raise NoSessionError("Failed to get the thread context")

    return ctx.session_id


def get_this_session_info() -> Optional[SessionInfo]:
    # Both lookups can fail when called outside a live Streamlit run
    # (e.g. unit tests, or worker threads spawned before a Runtime exists).
    # Return None so callers can no-op rather than crash.
    try:
        session_id = get_session_id()
        return Runtime.instance()._session_mgr.get_session_info(session_id)  # type: ignore
    except (NoSessionError, RuntimeError):
        return None


def get_script_run_count(session_info: SessionInfo) -> int:
    """Returns `session_info.script_run_count`.

    See https://github.com/whitphx/streamlit-webrtc/issues/709 for the
    history behind this helper (older Streamlit used `report_run_count`).
    """
    script_run_count = getattr(session_info, "script_run_count", None)
    if not isinstance(script_run_count, int):
        raise ValueError(
            f"script_run_count is unexpectedly not integer: {str(script_run_count)}"
        )
    return script_run_count
