# 01 — Bump `streamlit` minimum to 1.39.0

## Goal

Drop the minimum Streamlit version from `1.4.0` (Feb 2022) to `1.39.0` (Sep 2024) so the multi-year compatibility layer in `_compat.py` and its callers can be deleted. This is the single biggest reduction in accidental complexity in the codebase.

## Why 1.39.0

| Version | Why it's a candidate |
|---|---|
| 1.36.0 | Official `on_change` for components lands. Our `register_callback` hack becomes optional. |
| **1.39.0** | The `register_callback` hack **stops working** entirely. Anything <1.39.0 forces us to keep the hack — and the only people who use that path are users on Streamlit between 1.36.0–1.38.x, a narrow window. Cleaner to require ≥1.39.0 and delete the hack. |

Latest Streamlit (`develop`) requires `python>=3.10`, identical to us. Bumping ~20 months of Streamlit history off the support floor is reasonable for a major-ish version of `streamlit-webrtc`.

## Edit

`pyproject.toml`:

```toml
dependencies = [
    "streamlit>=1.39.0",  # was: 1.4.0
    ...
]
```

## Code to delete entirely

- `streamlit_webrtc/_compat.py` — every `VER_GTE_*` flag and every `try/except ModuleNotFoundError` import-chain. Replace with direct imports from the modern paths:
  - `from streamlit.runtime.app_session import AppSession, AppSessionState`
  - `from streamlit.runtime.session_manager import ActiveSessionInfo as SessionInfo`
  - `from streamlit.runtime.scriptrunner import get_script_run_ctx`
  - `from streamlit import rerun`
  - `from streamlit import cache_data`
- `streamlit_webrtc/server.py` — the `get_current_server()` + `gc.get_objects()` walk only exists for Streamlit <1.14. After the bump, callers can use `Runtime.instance()` directly.
- `streamlit_webrtc/components_callbacks.py` — the `register_widget` monkey-patch. Real maintenance hazard.

## Code to simplify

- `streamlit_webrtc/eventloop.py` — collapse `get_global_event_loop()` to just:
  ```python
  from streamlit.runtime.runtime import Runtime
  def get_global_event_loop():
      return Runtime.instance()._get_async_objs().eventloop
  ```
  Drop the `tornado.platform.asyncio.BaseAsyncIOLoop` import (only needed for <1.12).
- `streamlit_webrtc/session_info.py` — collapse `get_this_session_info()` to the `_session_mgr.get_session_info()` branch only. In `get_script_run_count`, drop the `report_run_count` fallback (only needed for <1.6).
- `streamlit_webrtc/relay.py` — drop both fallback branches; `singleton = Runtime.instance()` is the only one needed.
- `streamlit_webrtc/component.py`:
  - Remove the `if not VER_GTE_1_36_0: register_callback(...)` branch. Always use the `on_change` kwarg. Drop the `register_callback` import.
  - Remove the streamlit==0.84.0 HOTFIX (lines ~533-540, `isinstance(component_value_raw, str)` branch — drop the `json.loads` fallback and `LOGGER.warning("The component value is of type str")`).

## Dev-dep cleanup

`pyproject.toml`, in `[dependency-groups].dev`:
- Drop `altair<5 ; python_version < '3.11'`.
- Drop `protobuf<=3.20 ; python_version < '3.11'`.

Both pins exist only to make ancient Streamlit installable on the 3.10 matrix entries.

## CI matrix cleanup

`.github/workflows/test-build.yml` — delete every `include:` entry under the matrix (the rows pinning Streamlit 1.4.0 / 1.6.0 / 1.8.0 / 1.12.0 / 1.12.1 / 1.14.0 / 1.18.0 / 1.27.0 / 1.34.0). Keep the base `python-version` row only.

## Tests to update

- `tests/conftest.py` — the `if ST_VERSION < version.parse("1.55.0")` branch sets `command_line=None`; that's a different version concern (Streamlit 1.55 removed `command_line` from `RuntimeConfig`). Leave that alone in this PR.
- `tests/session_info_test.py` — `from streamlit_webrtc.server import VER_GTE_1_12_0` will break. Replace the test to always use the `client=Mock()` form. The whole `if VER_GTE_1_12_0` branch can go.

## Acceptance criteria

- `uv run pytest` green.
- `pre-commit run --all-files` green.
- `_compat.py`, `server.py`, `components_callbacks.py` no longer exist (or `_compat.py` is reduced to a stub of direct imports only — preference for full deletion and inlining at call sites).
- CI matrix has no `include:` rows pinning old Streamlit.
- Changelog fragment under `changelog.d/` documenting the bump.

## Risk notes

- **User-visible breaking change**: users on `streamlit<1.39.0` will have to pin `streamlit-webrtc` to an older version. Call this out in the changelog and consider a minor-version-only bump if the user wants extra caution (note: this project is pre-1.0, so a minor bump is the "breaking" signal).
- Verify the imports actually exist in 1.39.0 — `streamlit.runtime.runtime.Runtime`, `streamlit.runtime.session_manager.ActiveSessionInfo`, `streamlit.runtime.scriptrunner.get_script_run_ctx`, `streamlit.runtime.app_session.AppSession/AppSessionState`. (They were stable well before 1.39.0, but a sanity check is cheap.)

## Estimated impact

~300 lines of code deleted across 6 files. Zero behavior change for users on Streamlit ≥1.39.0.
