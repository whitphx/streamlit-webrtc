pkg/build:
	python scripts/release_check.py streamlit_webrtc/component.py
	cd streamlit_webrtc/frontend && npm run build
	poetry build

format:
	isort .
	black .
	flake8
