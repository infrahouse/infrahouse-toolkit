.DEFAULT_GOAL := help

define BROWSER_PYSCRIPT
import os, webbrowser, sys

from urllib.request import pathname2url

webbrowser.open("docs/_build/html/index.html")
endef
export BROWSER_PYSCRIPT

define PRINT_HELP_PYSCRIPT
import re, sys

for line in sys.stdin:
	match = re.match(r'^([a-zA-Z_-]+):.*?## (.*)$$', line)
	if match:
		target, help = match.groups()
		print("%-20s %s" % (target, help))
endef
export PRINT_HELP_PYSCRIPT

BROWSER := python -c "$$BROWSER_PYSCRIPT"
OS_VERSION ?= jammy

PWD := $(shell pwd)
ARCH := $(shell uname -m)

help:
	@python -c "$$PRINT_HELP_PYSCRIPT" < $(MAKEFILE_LIST)


.PHONY: pip
pip:
	pip install -U "pip ~= 23.0"

.PHONY: pip-tools
pip-tools: pip
	pip install -U "pip-tools ~= 6.6"

.PHONY: setuptools
setuptools: pip
	pip install -U "setuptools ~= 62.3.2"

.PHONY: hooks
hooks:
	mkdir -p .git/hooks
	test -f .git/hooks/pre-commit || cp hooks/pre-commit .git/hooks/pre-commit
	chmod 755 .git/hooks/pre-commit

.PHONY: bootstrap
bootstrap: hooks pip setuptools ## bootstrap the development environment
	pip install -r requirements.txt -r requirements_dev.txt
	pip install --editable .


.PHONY: install-infrahouse-repo
install-infrahouse-repo:
	# Install dependencies
	apt-get update
	apt-get install gpg lsb-release curl
	# Add a GPG public key to verify InfraHouse packages
	mkdir -p /etc/apt/cloud-init.gpg.d/
	curl  -fsSL https://release-$(lsb_release -cs).infrahouse.com/DEB-GPG-KEY-release-$(lsb_release -cs).infrahouse.com \
		| gpg --dearmor -o /etc/apt/cloud-init.gpg.d/infrahouse.gpg
	# Add the InfraHouse repository source
	echo "deb [signed-by=/etc/apt/cloud-init.gpg.d/infrahouse.gpg] https://release-$(lsb_release -cs).infrahouse.com/ $(lsb_release -cs) main" \
		> /etc/apt/sources.list.d/infrahouse.list
	apt-get update

.PHONY: clean
clean: clean-build clean-pyc clean-test ## remove all build, test, coverage and Python artifacts

.PHONY: clean-build
clean-build:
	rm -fr build/
	rm -fr dist/
	rm -fr omnibus-infrahouse-toolkit/pkg/
	rm -fr .eggs/
	find . -name '*.egg-info' -exec rm -fr {} +
	find . -name '*.egg' -exec rm -f {} +

.PHONY: clean-pyc
clean-pyc:
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +

.PHONY: clean-test
clean-test:
	rm -fr .tox/
	rm -f .coverage
	rm -fr htmlcov/
	rm -fr .pytest_cache

.PHONY: black
black: ## reformat code with black
	black infrahouse_toolkit setup.py

.PHONY: isort
isort: ## reformat imports
	isort infrahouse_toolkit setup.py

.PHONY: reqsort
reqsort: ## sort requirements files
	for f in requirements.txt requirements_dev.txt; do tmp_file=$$(tempfile) && sort $$f > "$$tmp_file" && mv "$$tmp_file" $$f; done

.PHONY: mdformat
mdformat: ## format markdown files
	mdformat .github

.PHONY: lint
lint: lint/yaml lint/black lint/isort lint/mdformat lint/reqsort lint/pylint ## check style

.PHONY: lint/yaml
lint/yaml: ## check style with yamllint
	yamllint infrahouse_toolkit .github .readthedocs.yaml

.PHONY: lint/black
lint/black: ## check style with black
	black --check --diff infrahouse_toolkit setup.py

.PHONY: lint/isort
lint/isort: ## check imports formatting
	isort --check-only infrahouse_toolkit setup.py

.PHONY: lint/mdformat
lint/mdformat:
	mdformat --check .github

.PHONY: lint/reqsort
lint/reqsort: ## check requirements sorting order
	@set -e ; for f in requirements.txt requirements_dev.txt; do test "$$(sort $$f)" = "$$(cat $$f)" || (echo "$$f is not sorted, run make reqsort" ; exit 1); done

.PHONY: lint/pylint
lint/pylint: ## check style with pylint
	pylint infrahouse_toolkit setup.py


.PHONY: test
test: ## run tests quickly with the default Python
	set
	pytest --cov \
		--cov-report=term-missing --cov-report=xml  \
		-xvvs infrahouse_toolkit

.PHONY: docs
docs: ## generate Sphinx HTML documentation, including API docs
	sphinx-apidoc -o docs/ infrahouse_toolkit
	$(MAKE) -C docs clean
	$(MAKE) -C docs html
	$(BROWSER) docs/_build/html/index.html

.PHONY: release
release: dist ## Build a Python packager and upload a release to PyPI
	twine upload dist/*

.PHONY: package
package:
	docker run \
	-v ${PWD}:/infrahouse-toolkit \
	--name infrahouse-toolkit-builder \
	--rm \
	"twindb/omnibus-ubuntu:${OS_VERSION}-${ARCH}" \
	bash -l /infrahouse-toolkit/omnibus-infrahouse-toolkit/omnibus_build.sh

.PHONY: dist
dist: clean ## builds source and wheel package
	python setup.py sdist
	python setup.py bdist_wheel
	ls -l dist

.PHONY: docker
docker:  ## Run a docker container with Ubuntu for local development.
	docker run -it --rm \
	-v $(PWD):/infrahouse-toolkit \
	-w /infrahouse-toolkit \
	python:3.11 bash -l

.PHONY: venv
venv: ## Create local python virtual environment
	python3 -m venv .venv
	@echo "To activate run"
	@echo ""
	@echo ". .venv/bin/activate"
