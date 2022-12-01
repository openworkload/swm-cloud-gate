.PHONY: prepare-venv
.ONESHELL:
prepare-venv: .SHELLFLAGS := -euo pipefail -c
prepare-venv: SHELL := bash
prepare-venv:
	python3 -m pip install 'virtualenv>=16.4.3'
	virtualenv --system-site-packages .venv
	VENV_BIN=.venv/bin
	$${VENV_BIN}/pip install --ignore-installed --no-deps -r requirements.txt

.PHONY: check
check:
	VENV_BIN=.venv/bin
	if [ ! -f "$${VENV_BIN}/black" ]; then
		make prepare-venv || true
	fi
	$${VENV_BIN}/flake8 --exclude .venv .
	$${VENV_BIN}/black --check --diff --exclude .venv --line-length 120 .

.PHONY: format
format:
	VENV_BIN=.venv/bin
	if [ ! -f "$${VENV_BIN}/black" ]; then
		make prepare-venv || true
	fi
	$${VENV_BIN}/isort --gitignore .
	$${VENV_BIN}/black --exclude .venv --line-length 120 .

.PHONY: requirements
requirements: requirements.txt
	make prepare-venv || true

requirements.txt: requirements.in
	@pip-compile $<
