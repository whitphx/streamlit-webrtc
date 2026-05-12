# 07 — Refactor the `webrtc_streamer()` function body

## Goal

`webrtc_streamer()` (`streamlit_webrtc/component.py:406-675`) mixes five separable concerns in one ~270-line function. Splitting them into named helpers makes the orchestration loop readable and individually testable.

**Do this after item 05** so layer-4 (`AppTest`) smoke tests can catch regressions.

## The five concerns

| # | Concern | Current line range |
|---|---|---|
| 1 | Get-or-create the per-key `WebRtcStreamerContext` in `st.session_state` | 476-498 |
| 2 | Render the frontend component, including the `on_change` plumbing | 499-531 |
| 3 | Restore the component value snapshot across `rerun()` | 532-565 |
| 4 | Worker lifecycle — stop on idle, create on incoming offer, flush SDP answer | 567-657 |
| 5 | Forward updated callbacks to a running worker | 662-673 |

After extraction, the body looks roughly like:

```python
def webrtc_streamer(key, mode=..., **kwargs) -> WebRtcStreamerContext:
    _apply_argument_defaults_and_deprecations(kwargs)
    context = _get_or_create_context(key)
    component_value = _render_frontend(key, context, **frontend_kwargs(kwargs))
    component_value = _restore_snapshot_if_needed(context, component_value)
    _handle_worker_lifecycle(context, component_value, key, **worker_kwargs(kwargs))
    _handle_ice_candidates(context, component_value)
    _update_callbacks(context, **callback_kwargs(kwargs))
    return context
```

Total orchestration: ~30 lines.

## Specific extractions

### `_get_or_create_context(key)`

Takes the session-state slot, validates the existing object's type via the `type(...).__name__ == ...` trick (with a comment explaining *why* — it's a real Streamlit hot-reload quirk), creates a fresh `WebRtcStreamerContext` if absent.

### `_render_frontend(key, context, ...)` → component value dict or None

Builds the on-change callback, wires it via `on_change=...` (after item 01 deletes the `register_callback` branch), calls `_component_func(...)`, returns the raw component value.

Sub-helper: `_make_on_change_callback(key, frontend_key, user_on_change)` returns the closure currently inlined at line 501.

### `_restore_snapshot_if_needed(context, component_value)`

The `ComponentValueSnapshot` dance for `rerun()` survivability (lines 542-565). Pure function of inputs and the context's prior snapshot; no Streamlit calls except `get_this_session_info` / `get_script_run_count`.

### `_handle_worker_lifecycle(context, component_value, key, ...)`

Three sub-cases handled in sequence:

1. **Stop**: when not playing and not signalling and a worker exists → stop it, clear SDP, `rerun()`.
2. **Create**: when no worker but there's an SDP offer → resolve RTC config, instantiate `WebRtcWorker`, call `process_offer`, store on context. Wrap in the existing `context._worker_creation_lock` block.
3. **Flush answer**: when a worker exists and has a `localDescription` not yet sent → set `context._sdp_answer_json`, `rerun()`.

This is the function that benefits most from splitting; it's also the one with the most subtle threading. Keep the existing comments on `rerun()` placement (lines 652-657) — they encode real bugs the current shape avoids.

### `_handle_ice_candidates(context, component_value)`

One-liner wrapper:

```python
def _handle_ice_candidates(context, component_value):
    worker = context._get_worker()
    if worker and component_value and component_value.get("iceCandidates"):
        worker.set_ice_candidates_from_offerer(component_value["iceCandidates"])
```

### `_update_callbacks(context, video_frame_callback=..., ...)`

Wraps lines 662-673. Could even use the consolidated `_update_callbacks` from item 06.

## Type signatures

Keep `webrtc_streamer()`'s overloads exactly as they are — the signature is the public API. Only the body changes.

## What to *not* extract

- The arg-defaulting block (lines 462-474, `if frontend_rtc_configuration is None: ...`) is short and inline-readable. Leaving it is fine.
- The deprecation warnings block (lines 442-460) goes away entirely after item 02.

## Verification

- All pytest layers from item 05 must pass.
- Manual smoke: run `home.py` and at least one app from `pages/` end-to-end in each of SENDRECV / SENDONLY / RECVONLY.
- Verify the `rerun()` workaround for component-value-loss-after-rerun still works: have two `webrtc_streamer()` instances on the same page and trigger a rerun from the first one (this is what the snapshot logic exists for).

## Acceptance criteria

- `webrtc_streamer()` body ≤ 50 lines.
- Each extracted helper has a one-paragraph docstring describing its concern.
- No behavior change in tests or in manual smoke testing.
- `uv run pytest` and `pre-commit` green.

## Risk notes

- Medium-risk. The worker lifecycle has subtle threading interactions (the lock, the `rerun()` placement). Read the inline comments on lines 589, 652-657 carefully before moving anything.
- This change is purely structural — there should be zero diff in the *behavior* the frontend sees.
