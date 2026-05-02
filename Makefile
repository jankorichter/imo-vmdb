.PHONY: build

build:
	poetry install --extras docs
	poetry run sphinx-build -M html docs imo_vmdb/built_docs
	poetry build
