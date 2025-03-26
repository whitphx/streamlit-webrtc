pkg/build:
	python scripts/release_check.py streamlit_webrtc/component.py
	cd streamlit_webrtc/frontend && pnpm run build
	uv build

format:
	uv run ruff format .
	uv run ruff check . --fix
