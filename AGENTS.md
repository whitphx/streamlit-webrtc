# AGENTS.md

This file provides guidance for Codex (and other AI agents) working in this repository. Its scope covers the entire repo.
- For repository-wide policies and detailed workflows (including releases and changelogs), defer to the canonical guidance in `CONTRIBUTING.md`.

## Quickstart
- Install dependencies with `uv sync`.
- Install Git hooks: `pre-commit install`.
- Use `make format` before committing to format both backend and frontend code.

## Running the project
- For local frontend development, set `_RELEASE = False` in `streamlit_webrtc/component.py` (do not commit this change) and run:
  - `cd streamlit_webrtc/frontend && pnpm dev`
  - In another terminal: `streamlit run home.py`

## Testing
- Backend tests: `uv run pytest`
- Frontend tests: `cd streamlit_webrtc/frontend && pnpm test`

## Type checking
- Run `uv run mypy .` for backend typing.

## Building
- Full build: `make build`
- Frontend-only build: `cd streamlit_webrtc/frontend && pnpm run build`

## Changelog fragments (required for every PR)
- **Every PR must include a changelog fragment under `changelog.d/`.** This is mandatory — the release pipeline collects fragments to build the next release's changelog, and a PR without one will not be reflected in the release notes.
- Create one with `uv run scriv create --edit`. It writes a timestamped file (e.g. `changelog.d/20260513_042424_<user>_<slug>.md`) prefilled with the available categories.
- Pick **one** category and delete the rest:
  - `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security` — for user-visible changes.
  - `Chore` — for internal changes that don't affect users (refactors, dead-code cleanup, tooling, CI, build infra, internal docs).
- Write a single bullet describing the change. For user-visible categories, write it from the user's perspective; for `Chore`, from the maintainer's. Reference the issue or PR where it adds context.
- Commit the fragment as part of the same PR — not as a follow-up.
- CI opens a changelog preview PR from committed fragments; maintainers merge it before the automated release build runs.

## Contribution notes
- Keep changes minimal and focused; prefer small, reviewable commits.
- Follow existing code patterns and naming conventions in each area.
