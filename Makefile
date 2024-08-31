PYTHON=python3.10
RUNTEST=$(PYTHON) -m unittest -v -b
VENV_BIN=.venv/bin
ALLMODULES=$(patsubst %.py, %.py, $(wildcard test_*.py))

.PHONY: prepare-venv
.ONESHELL:
prepare-venv: .SHELLFLAGS := -euo pipefail -c
prepare-venv: SHELL := bash
prepare-venv:
	$(PYTHON) -m pip install 'virtualenv>=16.4.3'
	virtualenv --system-site-packages .venv
	$(VENV_BIN)/pip install --ignore-installed --no-deps -r requirements.txt

.PHONY: check
check:
	$(VENV_BIN)/flake8 swmcloudgate test
	$(VENV_BIN)/black --check --diff --exclude .venv swmcloudgate test
	$(VENV_BIN)/ruff swmcloudgate test
	$(VENV_BIN)/bandit -r swmcloudgate -c "pyproject.toml" --silent

.PHONY: format
format:
	. $(VENV_BIN)/activate
	$(VENV_BIN)/autoflake -i -r --ignore-init-module-imports swmcloudgate test
	$(VENV_BIN)/isort --gitignore swmcloudgate test
	$(VENV_BIN)/black --exclude .venv swmcloudgate test

.PHONY: package
package:
	. .venv/bin/activate
	$(PYTHON) -m build

.PHONY: upload
upload:
	. .venv/bin/activate
	$(PYTHON) -m twine upload --verbose --config-file .pypirc dist/*

.PHONY: clean
clean:
	rm -fr ./dist
	rm -fr ./swmcloudgate.egg-info
	rm -fr ./build

.PHONY: test
test:
	. $(VENV_BIN)/activate
	$(RUNTEST) $(ALLMODULES)

% : test/test_%.py
	. $(VENV_BIN)/activate
	$(RUNTEST) test/test_$@.py

.PHONY: requirements
requirements: requirements.txt
	make prepare-venv || true

requirements.txt: requirements.in
	@pip-compile $<
