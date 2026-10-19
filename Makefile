
.PHONY: run test lint check build

run:
	uv run uvicorn app.main:app --reload

test:
	uv run pytest

lint:
	uv run ruff check .

check:
	uv run python -m compileall -q app scripts
	uv run ruff check .
	uv run ty check

build:
	uv build
