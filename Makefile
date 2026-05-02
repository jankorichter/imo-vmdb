.PHONY: build test

build: test
	poetry install --extras docs
	poetry run sphinx-build -b html docs imo_vmdb/built_docs
	poetry build

test:
	poetry run pytest
