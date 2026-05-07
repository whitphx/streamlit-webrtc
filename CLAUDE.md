# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is `streamlit-webrtc`, a Streamlit component that enables real-time video and audio processing using WebRTC. The library allows developers to build web apps that can capture, process, and stream video/audio data in real-time directly in the browser.

## Development Commands

### Setup
```bash
# Install dependencies
uv sync

# Install pre-commit hooks
pre-commit install
```

### Running Development Server
```bash
# Set _RELEASE = False in streamlit_webrtc/component.py (development only, don't commit)

# Start frontend dev server
cd streamlit_webrtc/frontend
pnpm dev

# In another terminal, run the main app
streamlit run home.py
```

### Testing
```bash
# Run Python tests
uv run pytest

# Run frontend tests
cd streamlit_webrtc/frontend
pnpm test
```

### Code Quality
```bash
# Format backend code
make format/backend
# Or individually:
uv run ruff format .
uv run ruff check . --fix

# Format frontend code
make format/frontend
# Or individually:
cd streamlit_webrtc/frontend
pnpm format

# Format all code
make format

# Type checking
uv run mypy .
```

### Building
```bash
# Build the complete package (frontend + backend)
make build

# Frontend build only
cd streamlit_webrtc/frontend
pnpm run build
```

## Architecture

### Core Components

- **`streamlit_webrtc/component.py`**: Main Streamlit component interface (`webrtc_streamer`)
- **`streamlit_webrtc/webrtc.py`**: WebRTC connection management and worker processes
- **`streamlit_webrtc/models.py`**: Data models and base classes for processors
- **`streamlit_webrtc/process.py`**: Audio/video processing tracks and transformations
- **`streamlit_webrtc/factory.py`**: Factory functions for creating processing tracks

### Frontend Structure

- **React/TypeScript frontend** in `streamlit_webrtc/frontend/`
- **Vite** for bundling and development
- **Material-UI** components for UI
- **WebRTC adapter** for cross-browser compatibility

### Key Abstractions

- **Processors**: `VideoProcessorBase` and `AudioProcessorBase` for frame-by-frame processing
- **Tracks**: MediaStreamTrack implementations for audio/video streams
- **WebRtcWorker**: Manages WebRTC connections and media processing
- **Component Context**: `WebRtcStreamerContext` for accessing stream state

### Processing Flow

1. Browser captures media via WebRTC
2. Frames are sent to Python backend
3. Custom processors transform frames (video/audio)
4. Processed frames are sent back to browser
5. Browser displays/plays the processed media

## Development Notes

### Release Process
- Edit `CHANGELOG.md` first
- Use `make release/patch`, `make release/minor`, or `make release/major`
- CI/CD automatically builds and publishes on tag push

### Frontend Development
- Set `_RELEASE = False` in `component.py` for local development
- Frontend dev server runs on different port than production build
- Component loads development build when `_RELEASE = False`

### Testing Strategy
- Python tests in `tests/` directory using pytest
- Frontend tests using Vitest and React Testing Library
- Example apps in `pages/` for manual testing

### WebRTC Configuration
- STUN/TURN server configuration via `rtc_configuration`
- Default uses Google's public STUN server
- Production deployments may need TURN servers (e.g., Twilio)

## OSS Issue Automation Rules

This repository uses GitHub Actions to let Claude handle initial issue triage and a portion of the implementation work. When Claude works from an issue, follow these rules:

- **Avoid breaking changes to the public API**: be especially careful with `webrtc_streamer()` arguments, the `VideoProcessorBase` / `AudioProcessorBase` contract, and the `WebRtcStreamerContext` interface. If a breaking change is required, stop the implementation and ask for discussion in the issue.
- **Discuss new dependencies first**: any new entry in `pyproject.toml` must be agreed upon in the issue beforehand. Prefer the standard library when possible.
- **License compatibility**: do not bring in code that is not MIT-compatible.
- **Always add a changelog fragment**: add an entry under `changelog.d/` for any user-visible change.
- **Tests and linters**: confirm that `uv run pytest` and `pre-commit run --all-files` pass locally before opening a PR.
- **Stop on unclear design decisions**: when in doubt, stop and ask the maintainer in the issue.
- **Streamlit / aiortc / PyAV compatibility**: respect the existing dependency ranges in `pyproject.toml` and only widen them carefully when truly necessary.