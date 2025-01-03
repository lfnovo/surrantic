.PHONY: ruff lint test test-integration test-unit test-all

lint:
	uv run python -m mypy .

ruff:
	ruff check . --fix

test-integration:
	uv run pytest -v -m integration

test-unit:
	uv run pytest -v -m "not integration"

test-all:
	uv run pytest -v

test: test-unit
