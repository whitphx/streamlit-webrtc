# 01 — Bump `streamlit` minimum to match the active Python floor

## Goal

Set the minimum supported Streamlit version to the oldest Streamlit that itself requires Python ≥ our minimum active Python. Anything older accepts Python versions we no longer support, so its compatibility code is dead weight. Then delete the now-dead branches in `_compat.py` and its callers.

The `_compat.py` *layer* stays — encapsulating Streamlit-internal imports there is cheap and keeps the rest of the codebase decoupled from Streamlit's module layout. What goes is the version-conditional fallback branches inside it (and in its callers) that target Streamlit versions we no longer need to support.

## Why this floor

| Question | Answer (as of 2026-05-13) |
|---|---|
| Lowest Python in active support? | **3.10** — Python 3.9 reached EOL on 2025-10-31. 3.10 is in security phase until 2026-10. |
| Oldest Streamlit that requires Python ≥ 3.10? | **1.51.0** (released 2025-10-29). Streamlit 1.50.0 had `requires-python = "!=3.9.7,>=3.9"`; 1.51.0 bumped to `>=3.10` after merging streamlit/streamlit#12773. |

→ **Min Streamlit = 1.51.0.**

When Python 3.10 itself goes EOL (Oct 2026), repeat the exercise: bump our floor to 3.11 and Streamlit's first 3.11-only release.

## Edit

`pyproject.toml`:

```toml
dependencies = [
    "streamlit>=1.51.0",  # First Streamlit version requiring Python >=3.10
    ...
]
```

## Code to delete entirely

- `streamlit_webrtc/server.py` — `get_current_server()` + the `gc.get_objects()` walk only exists for Streamlit <1.14. With min 1.51, no caller needs it.
- `streamlit_webrtc/components_callbacks.py` — the `register_widget` monkey-patch is only used in `component.py` for Streamlit <1.36. With min 1.51, the official `on_change` kwarg is always available.

## Code to simplify

- `streamlit_webrtc/_compat.py` — collapse every `try/except ModuleNotFoundError` chain to its first (modern) branch. Drop every `VER_GTE_*` flag (each flag's threshold is well below 1.51).
- `streamlit_webrtc/eventloop.py` — `get_global_event_loop()` collapses to one branch:
  ```python
  from streamlit.runtime.runtime import Runtime
  def get_global_event_loop():
      return Runtime.instance()._get_async_objs().eventloop
  ```
  Drop the `tornado.platform.asyncio.BaseAsyncIOLoop` import (only needed for <1.12).
- `streamlit_webrtc/session_info.py` — `get_this_session_info()` collapses to the `_session_mgr.get_session_info()` branch only. In `get_script_run_count`, drop the `report_run_count` fallback (only needed for <1.6).
- `streamlit_webrtc/relay.py` — drop both fallback branches; `singleton = Runtime.instance()` is the only one needed.
- `streamlit_webrtc/component.py` — remove the `if not VER_GTE_1_36_0: register_callback(...)` branch. Always pass `on_change=callback`. Drop the `register_callback` import.

## Dev-dep cleanup

`pyproject.toml`, in `[dependency-groups].dev`:
- Drop `altair<5 ; python_version < '3.11'`.
- Drop `protobuf<=3.20 ; python_version < '3.11'`.

Both pins exist only to make ancient Streamlit installable on the 3.10 matrix entries.

## CI matrix cleanup

`.github/workflows/test-build.yml`:
- Drop the `streamlit-version: [""]` matrix dimension and the entire `include:` block (the rows pinning Streamlit 1.4.0 / 1.6.0 / 1.8.0 / 1.12.0 / 1.12.1 / 1.14.0 / 1.18.0 / 1.27.0 / 1.34.0).
- Drop the `Install a specific version of Streamlit` step (used only by the now-removed include rows).
- Drop the `--with "setuptools<81"` workaround on the pytest step (only needed because Streamlit 1.4.0 imported `pkg_resources`).

## Tests to update

- `tests/session_info_test.py` — `from streamlit_webrtc.server import VER_GTE_1_12_0` will break. Both branches collapse to the single modern path.
- `tests/conftest.py` — the `if ST_VERSION < version.parse("1.55.0")` branch sets `command_line=None`. Streamlit 1.51-1.54 still need this, so leave it.

## Acceptance criteria

- `uv run pytest` green.
- `pre-commit run --all-files` green.
- `actionlint .github/workflows/test-build.yml` shows no *new* warnings (pre-existing ones in `set-build-info` are out of scope).
- `_compat.py` retained as a thin re-export module; no `VER_GTE_*` flags or fallback branches.
- `server.py`, `components_callbacks.py` deleted.
- CI matrix has no `include:` rows and no `streamlit-version` dimension.
- Changelog fragment under `changelog.d/` documenting the bump.

## Risk notes

- **User-visible breaking change**: users on `streamlit<1.51.0` will need to pin `streamlit-webrtc` to an older release. Call out in the changelog.
- Verify the imports actually exist in 1.51.0 — `streamlit.runtime.runtime.Runtime`, `streamlit.runtime.session_manager.ActiveSessionInfo`, `streamlit.runtime.scriptrunner.get_script_run_ctx`, `streamlit.runtime.app_session.AppSession/AppSessionState`. (All stable well before 1.51.)

## Estimated impact

~300 lines of code deleted across ~6 files. Zero behavior change for users on Streamlit ≥ 1.51.0.
