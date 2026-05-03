.PHONY: build docs test

build: test docs
	poetry build

test:
	poetry run pytest

docs:
	poetry install --extras docs
	poetry run sphinx-build -b html docs imo_vmdb/built_docs