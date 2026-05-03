.PHONY: build docs lint test

build: lint test docs
	poetry build

lint:
	poetry run ruff check .
	poetry run ruff format --check .

test:
	poetry run pytest

docs:
	poetry install --extras docs
	poetry run sphinx-build -b html docs imo_vmdb/built_docs