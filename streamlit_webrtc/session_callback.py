"""Run user callbacks that fire when a media track ends.

These callbacks fire on Streamlit's shared asyncio loop or on a background
thread, where no ``ScriptRunContext`` is attached, so ``st.session_state``
would not reach the session that registered them. They run here on a
dedicated thread with the registering session's context attached for the
duration of the call.

Attaching a context to a custom thread follows
https://docs.streamlit.io/develop/concepts/design/multithreading#option-2-expose-scriptruncontext-to-the-thread,
which Streamlit documents as not officially supported. Its warning is about
a context outliving its script run, and that is the case here: the callback
usually fires after the run that registered it has finished. So the callback
gets a copy of the context that can read and write the session's state but
cannot send UI messages to the browser or request a rerun.
"""

import contextlib
import dataclasses
import itertools
import logging
import threading
from typing import Callable, Iterator, Optional

from ._compat import (
    SCRIPT_RUN_CONTEXT_ATTR_NAME,
    ScriptRunContext,
    add_script_run_ctx,
    get_script_run_ctx,
)

logger = logging.getLogger(__name__)

_thread_id_generator = itertools.count()


def _drop_forward_msg(msg: object) -> None:
    logger.warning(
        "Streamlit UI commands do not render from a callback that runs when "
        "a media track ends; the output was dropped."
    )


def _without_ui(ctx: ScriptRunContext) -> ScriptRunContext:
    # The registering script run may still be executing on its own thread,
    # sharing these objects with the callback. Fresh cursors keep a stray
    # `st.write()` from shifting that run's element positions, and without
    # `script_requests` a stray `st.rerun()` cannot interrupt it.
    try:
        return dataclasses.replace(
            ctx, _enqueue=_drop_forward_msg, cursors={}, script_requests=None
        )
    except TypeError:
        # A future Streamlit may rename these fields. State access matters
        # more than the guard, so fall back to the unguarded context.
        logger.debug("Could not copy ScriptRunContext; attaching it as is.")
        return ctx


@contextlib.contextmanager
def _script_run_ctx_attached(ctx: Optional[ScriptRunContext]) -> Iterator[None]:
    thread = threading.current_thread()
    previous = get_script_run_ctx(suppress_warning=True)
    if ctx is not None:
        add_script_run_ctx(thread, ctx)
    try:
        yield
    finally:
        # `add_script_run_ctx(thread, None)` would re-attach the current
        # context instead of clearing it, so restore the attribute directly.
        setattr(thread, SCRIPT_RUN_CONTEXT_ATTR_NAME, previous)


def call_with_script_run_ctx(
    callback: Callable[[], None], ctx: Optional[ScriptRunContext]
) -> None:
    """Call ``callback`` on the current thread with a guarded copy of ``ctx``
    attached, then restore whatever context the thread had before."""
    with _script_run_ctx_attached(_without_ui(ctx) if ctx is not None else None):
        callback()


def run_ended_callback(
    callback: Callable[[], None], ctx: Optional[ScriptRunContext], *, owner: str
) -> None:
    """Run a track-ended ``callback`` for the session that ``ctx`` belongs to,
    returning without waiting for it unless it runs inline."""
    current = get_script_run_ctx(suppress_warning=True)
    if current is not None and ctx is not None and current.session_id == ctx.session_id:
        # Stopped from the session's own script run, e.g. a factory source
        # track on STOP. Running inline keeps every `st.*` command working
        # and the result visible to the rest of this run, as it always was.
        _call_logging_errors(callback, owner)
        return

    def target() -> None:
        call_with_script_run_ctx(lambda: _call_logging_errors(callback, owner), ctx)

    thread = threading.Thread(
        target=target,
        name=f"{owner}_on_ended_{next(_thread_id_generator)}",
        daemon=True,
    )
    try:
        thread.start()
    except RuntimeError:
        # New threads cannot start once the interpreter is finalizing.
        logger.debug("Could not start a thread for %s.on_ended; running inline.", owner)
        _call_logging_errors(callback, owner)


def _call_logging_errors(callback: Callable[[], None], owner: str) -> None:
    try:
        callback()
    except Exception:
        logger.exception("%s: on_ended callback raised an exception", owner)
