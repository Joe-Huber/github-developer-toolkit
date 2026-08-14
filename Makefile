.PHONY: install check lint format format-check typecheck test coverage

## install        install the project and dev dependencies
install:
	uv sync

## check          run every quality gate (lint, format, typecheck, test)
check: lint format-check typecheck test

## lint           run the linter
lint:
	uv run ruff check .

## format         auto-format the code
format:
	uv run ruff format .

## format-check   verify formatting without modifying files
format-check:
	uv run ruff format --check .

## typecheck      run the static type checker
typecheck:
	uv run mypy src tests

## test           run the test suite
test:
	uv run pytest

## coverage       run tests with a coverage report
coverage:
	uv run pytest --cov=ghdtk --cov-report=term-missing
