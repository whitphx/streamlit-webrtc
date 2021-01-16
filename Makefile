pkg/build:
	python release_check.py streamlit_webrtc/__init__.py
	cd streamlit_webrtc/frontend && npm run build
	poetry build

format:
	isort .
	black .
	flake8
