
.PHONY: run test test-fast test-pg lint check build

run:
	uv run uvicorn app.main:app --reload

test:
	uv run pytest

test-fast:
	uv run pytest -m "not postgres"

test-pg:
	uv run pytest -m postgres

lint:
	uv run ruff check .

check:
	uv run python -m compileall -q app scripts
	uv run ruff check .
	uv run ty check

build:
	uv build
