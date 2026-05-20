.PHONY: build docs lint review test typecheck

build: review
	poetry build

review: lint typecheck test docs

lint:
	poetry run ruff check .
	poetry run ruff format --check .

typecheck:
	poetry run pyright

test:
	poetry run pytest

docs:
	poetry install --extras docs
	poetry run sphinx-build -b html docs imo_vmdb/built_docs