PYTHON=python3
RUNTEST=$(PYTHON) -m unittest -v -b
VENV_BIN=.venv/bin
ALLMODULES=$(patsubst %.py, %.py, $(wildcard test*.py))

.PHONY: prepare-venv
.ONESHELL:
prepare-venv: .SHELLFLAGS := -euo pipefail -c
prepare-venv: SHELL := bash
prepare-venv:
	python3 -m pip install 'virtualenv>=16.4.3'
	virtualenv --system-site-packages .venv
	$(VENV_BIN)/pip install --ignore-installed --no-deps -r requirements.txt

.PHONY: check
check:
	$(VENV_BIN)/flake8 app test
	$(VENV_BIN)/black --check --diff --exclude .venv app test
	$(VENV_BIN)/ruff app test
	$(VENV_BIN)/bandit -r app -c "pyproject.toml" --silent

.PHONY: format
format:
	$(VENV_BIN)/autoflake -i -r --ignore-init-module-imports app test
	$(VENV_BIN)/isort --gitignore app test
	$(VENV_BIN)/black --exclude .venv app test

.PHONY: test
test:
	. $(VENV_BIN)/activate
	$(RUNTEST) $(ALLMODULES)

% : test/test%.py
	. $(VENV_BIN)/activate
	$(RUNTEST) test/test$@

.PHONY: requirements
requirements: requirements.txt
	make prepare-venv || true

requirements.txt: requirements.in
	@pip-compile $<
