# 02 — Delete dead and expired code

## Goal

Remove code paths that are demonstrably dead, expired by their own deprecation notice, or working around bugs in versions no longer supported.

Each bullet is independently shippable. Group them into one PR or split — your call.

## 2.1 — `_test()` block at end of `webrtc.py`

**File**: `streamlit_webrtc/webrtc.py:776-826`

```python
def _test():
    ...

if __name__ == "__main__":
    ...
    _test()
```

This is dead. `_test()` calls `WebRtcWorker(mode=WebRtcMode.SENDRECV)` but the current `__init__` requires ~20 positional/keyword args — the call doesn't even import-check. It is not invoked from any test runner; only from the `__main__` block.

**Action**: delete both functions and the `__main__` guard. The replacement is in [05-add-pytest-layers.md](./05-add-pytest-layers.md). (Item 05 doesn't have to land in the same PR — this code is broken-as-is.)

## 2.2 — `video_transformer_factory` / `async_transform` deprecated kwargs

**File**: `streamlit_webrtc/component.py:443-460` (the body) plus the kwargs in each `@overload` and the main signature.

These have been deprecated since v0.20 (years ago). They emit `DeprecationWarning` and forward to the modern names.

**Action**: remove the kwargs entirely from all 4 `@overload`s and the main definition. Remove the forwarding `if` block. Drop the `import warnings` if no longer used. Add a changelog fragment under `Removed`.

**Risk**: any user still passing `video_transformer_factory=...` will get a `TypeError`. Acceptable for a major-ish bump (pre-1.0 minor). If you'd rather not break them, leave for a later, intentional cleanup pass.

## 2.3 — JSON-string HOTFIX for streamlit==0.84.0

**File**: `streamlit_webrtc/component.py:532-540`

```python
# HOTFIX: The return value from _component_func()
#         is of type str with streamlit==0.84.0.
# See https://github.com/whitphx/streamlit-webrtc/issues/287
component_value: Union[Dict, None]
if isinstance(component_value_raw, str):
    LOGGER.warning("The component value is of type str")
    component_value = json.loads(component_value_raw)
else:
    component_value = component_value_raw
```

Streamlit 0.84.0 is way below the new floor. Folds away after item 01.

**Action**: replace with `component_value: Union[Dict, None] = component_value_raw`. Drop the `import json` if it becomes unused (it's still used a few lines below for `json.dumps`, so leave it).

## 2.4 — `process.py:127` always-truthy `if`

**File**: `streamlit_webrtc/process.py:117-129`

```python
async def _fallback_recv_queued(self, frames: List[FrameT]) -> List[FrameT]:
    if len(frames) > 1:
        logger.warning(...)
    if self.processor.recv:        # ← always truthy (bound method)
        return [self.processor.recv(frames[-1])]
    return [frames[-1]]            # ← dead branch
```

`self.processor.recv` is always a bound method (defined on `ProcessorBase`). The `if` is always true; the fallback `return [frames[-1]]` is unreachable.

**Action**: drop the `if` and the dead `return`. Just `return [self.processor.recv(frames[-1])]`.

## 2.5 — `from streamlit_webrtc.server import VER_GTE_1_12_0` in tests

**File**: `tests/session_info_test.py:3`

This will break after item 01 deletes `server.py`. If item 01 isn't landing soon, fix here too: the test branches on `VER_GTE_1_12_0` (always true for any supported Streamlit), so collapse to one path.

## Acceptance criteria

- `uv run pytest` green.
- `pre-commit run --all-files` green.
- Changelog fragment for 2.2 (user-visible removal). Other items don't need fragments.

## Risk notes

- 2.2 is a user-visible breaking change. Bundle with item 01 if shipping together to amortize the breakage in one release.
- 2.1, 2.3, 2.4, 2.5 are non-breaking.
