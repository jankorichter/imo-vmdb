.PHONY: build docs lint review test

build: review
	poetry build

review: lint test docs

lint:
	poetry run ruff check .
	poetry run ruff format --check .

test:
	poetry run pytest

docs:
	poetry install --extras docs
	poetry run sphinx-build -b html docs imo_vmdb/built_docs