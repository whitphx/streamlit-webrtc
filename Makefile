pkg/build:
	python scripts/release_check.py streamlit_webrtc/component.py
	cd streamlit_webrtc/frontend && pnpm run build
	uv build

format/backend:
	uv run ruff format .
	uv run ruff check . --fix

format/frontend:
	cd streamlit_webrtc/frontend && pnpm format

format:
	$(MAKE) format/backend
	$(MAKE) format/frontend

release/patch:
	$(MAKE) version=patch release

release/minor:
	$(MAKE) version=minor release

release/major:
	$(MAKE) version=major release

release:
	uv run bump-my-version bump $(version) --tag --commit --commit-args='--allow-empty' --verbose
	git push
	git push --tags
