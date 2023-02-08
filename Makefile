.DEFAULT_GOAL := help

define BROWSER_PYSCRIPT
import os, webbrowser, sys

from urllib.request import pathname2url

webbrowser.open("file://" + pathname2url(os.path.abspath(sys.argv[1])))
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

.PHONY: upgrade-requirements
upgrade-requirements: pip-tools ## Upgrade requirements
	pip-compile --upgrade --verbose --output-file requirements.txt requirements.in
	pip-compile --upgrade --verbose --output-file requirements_dev.txt requirements_dev.in

.PHONY: bootstrap
bootstrap: pip pip-tools setuptools ## bootstrap the development environment
	pip-sync requirements.txt requirements_dev.txt
	pip install --editable .


.PHONY: clean
clean: clean-build clean-pyc clean-test ## remove all build, test, coverage and Python artifacts

.PHONY: clean-build
clean-build:
	rm -fr build/
	rm -fr dist/
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
	black infrahouse_toolkit

.PHONY: lint/pylint
lint/pylint: ## check style with flake8
	pylint infrahouse_toolkit tests

.PHONY: lint/black
lint/black: ## check style with black
	black --check infrahouse_toolkit

.PHONY: lint
lint: lint/black lint/pylint ## check style

.PHONY: test
test: ## run tests quickly with the default Python
	pytest -xvvs infrahouse_toolkit

.PHONY: docs
docs: ## generate Sphinx HTML documentation, including API docs
	rm -f docs/infrahouse_toolkit.rst
	rm -f docs/modules.rst
	sphinx-apidoc -o docs/ infrahouse_toolkit
	$(MAKE) -C docs clean
	$(MAKE) -C docs html
	$(BROWSER) docs/_build/html/index.html

.PHONY: release
release: dist ## package and upload a release
	twine upload dist/*

.PHONY: dist
dist: clean ## builds source and wheel package
	python setup.py sdist
	python setup.py bdist_wheel
	ls -l dist
