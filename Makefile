pkg/build:
	python scripts/release_check.py streamlit_webrtc/component.py
	cd streamlit_webrtc/frontend && pnpm run build
	uv build

format:
	uv run ruff format .
	uv run ruff check . --fix

docker/build:
# Set `--platform linux/amd64` because some packages do not work with Docker on M1 mac for now.
	docker build \
		--platform linux/amd64 \
		-t streamlit-webrtc \
		.

docker/run:
	docker run \
		--rm \
		-it \
		-p 8501:8501 \
		-v `pwd`:/srv \
		-e STREAMLIT_SERVER_FILE_WATCHER_TYPE=poll \
		streamlit-webrtc \
		uv run streamlit run home.py

docker/shell:
	docker run \
		--rm \
		-it \
		-p 8501:8501 \
		-v `pwd`:/srv \
		-e SHELL=/bin/bash \
		-e STREAMLIT_SERVER_FILE_WATCHER_TYPE=poll \
		streamlit-webrtc \
		bash
