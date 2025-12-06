# AGENTS.md

This file provides guidance for Codex (and other AI agents) working in this repository. Its scope covers the entire repo.

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

## Release notes
- Update `CHANGELOG.md` at the start of release work and use the `make release/*` targets.

## Contribution notes
- Keep changes minimal and focused; prefer small, reviewable commits.
- Follow existing code patterns and naming conventions in each area.
