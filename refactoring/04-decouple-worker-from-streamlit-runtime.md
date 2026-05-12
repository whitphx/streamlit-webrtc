# 04 — Decouple `WebRtcWorker` from the Streamlit runtime

## Goal

Make `WebRtcWorker` constructable in a pytest process *without* a Streamlit `Runtime.instance()` being present. This is the unlock for the unit/integration tests in item 05.

## Current coupling points

Inside `WebRtcWorker.__init__` and its descendant calls:

1. `streamlit_webrtc/webrtc.py:388` — `loop_context(get_global_event_loop())` reaches into `Runtime.instance()`.
2. `streamlit_webrtc/webrtc.py:454, 520` — `get_global_event_loop()` and `get_global_relay()` inside `_process_offer_thread_impl`.
3. `streamlit_webrtc/webrtc.py:653` — `get_global_event_loop()` inside `add_ice_candidate`.
4. `streamlit_webrtc/webrtc.py:764` — `get_global_event_loop()` inside `stop`.
5. `streamlit_webrtc/webrtc.py:427-429` — `SessionShutdownObserver(self.stop)` reaches into `get_this_session_info()`, which reaches into `Runtime.instance()`.

## Design

Accept the event loop and relay as constructor arguments. Default them to `None` and resolve from Streamlit lazily, so the public API doesn't change for existing users:

```python
class WebRtcWorker(Generic[...]):
    def __init__(
        self,
        mode: WebRtcMode,
        ...,
        # NEW — keyword-only, defaults to Streamlit-resolved
        loop: Optional[asyncio.AbstractEventLoop] = None,
        relay: Optional[MediaRelay] = None,
        session_shutdown_observer_factory: Optional[
            Callable[[Callable[[], None]], "SessionShutdownObserver"]
        ] = None,
    ) -> None:
        self._loop = loop or get_global_event_loop()
        self._relay = relay or get_global_relay()
        ...
        if session_shutdown_observer_factory is None:
            self._session_shutdown_observer = SessionShutdownObserver(self.stop)
        else:
            self._session_shutdown_observer = session_shutdown_observer_factory(self.stop)
```

Then replace every `get_global_event_loop()` call inside the worker with `self._loop`, and every `get_global_relay()` with `self._relay`. The Streamlit-runtime hop happens *once*, at construction.

For tests: pass `loop=asyncio.new_event_loop()`, `relay=MediaRelay()`, and a no-op `session_shutdown_observer_factory=lambda cb: _NoopObserver()`.

## Rules

- **Keyword-only.** Don't make these positional. Existing call sites in `component.py` continue to work without changes.
- **Streamlit code path unchanged.** When `loop=None` and `relay=None`, behavior matches today exactly.
- **Don't expose `_loop`/`_relay` as public attributes** unless you actually want them on the public API. Underscore-prefix them.
- `session_shutdown_observer_factory` is the awkward one — `SessionShutdownObserver.__init__` itself calls `get_this_session_info()`. The factory injection lets tests replace it with a no-op observer. If you'd rather not add the third parameter, an alternative is to make `SessionShutdownObserver` no-op gracefully when no session can be resolved (it kind of already does — `if session_info:` is the guard — confirm and document).

## Caveat: `loop_context` usage

`webrtc.py:388-389` uses `loop_context(get_global_event_loop())` to construct an `asyncio.Event` bound to the right loop. After the change this becomes `loop_context(self._loop)` — same effect.

`relay.py:23-26` creates the `MediaRelay` inside `loop_context(loop)`. After injection, if the caller supplies their own `MediaRelay`, they're responsible for having created it on the right loop. Document this in a docstring for the new `relay=` kwarg.

## Tests to keep green

- `tests/import_test.py` — must keep passing.
- `tests/source_test.py` — unrelated, must keep passing.
- `tests/session_info_test.py` — unrelated, must keep passing.

## Acceptance criteria

- `WebRtcWorker(...)` can be constructed with explicit `loop=` and `relay=` kwargs.
- No `get_global_event_loop()` or `get_global_relay()` call inside `WebRtcWorker` methods after construction (`__init__` is allowed to resolve defaults).
- No public-API change for `component.py` callers.
- `uv run pytest` green; `pre-commit run --all-files` green.

## Risk notes

- Medium-risk: touches every method that interacts with the loop. Take care that `asyncio.run_coroutine_threadsafe(coro, loop=...)` always uses `self._loop`, never a freshly-resolved one — otherwise tests would silently route across two different loops.
- Lands cleanly before or after item 01. Easier *after* 01 because the compat shims around `get_global_event_loop` are simpler.
