pkg/build:
	python scripts/release_check.py streamlit_webrtc/component.py
	cd streamlit_webrtc/frontend && npm run build
	poetry build

format:
	isort .
	black .
	flake8

docker/build/m1mac:
	docker build --platform linux/amd64 -t streamlit-webrtc .

docker/dev:
	docker run --rm -it -p 8501:8501 -v `pwd`:/srv streamlit-webrtc bash
