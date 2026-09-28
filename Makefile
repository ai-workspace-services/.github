.PHONY: validate
.ONESHELL:
SHELL := /bin/bash

validate:
	venv_dir="$$(mktemp -d)"
	trap 'rm -rf "$$venv_dir"' EXIT
	python3 -m venv "$$venv_dir"
	"$$venv_dir/bin/pip" install --disable-pip-version-check --quiet --requirement scripts/requirements.txt
	"$$venv_dir/bin/python" scripts/validate-capabilities.py
	"$$venv_dir/bin/python" scripts/test_capabilities.py
