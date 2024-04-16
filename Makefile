.PHONY: test build check format _poetry
.SILENT:

_poetry: _build/poetry.stamp
_build/poetry.stamp: poetry.lock
	poetry install --with=dev
	mkdir -p _build/
	touch $@

poetry.lock: pyproject.toml
	poetry lock --no-update
	touch $@

test: _poetry
	poetry run pytest

check: _poetry
	poetry run pyright src/

format: _poetry
	poetry run black --quiet src/

build:
	poetry build
