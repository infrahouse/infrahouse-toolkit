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
# The Ubuntu release that package-smoke-test installs the standalone package on.
STANDALONE_OS_VERSION ?= noble
# Python files outside the infrahouse_toolkit package that the linters check.
TOOLING_PY := setup.py packaging/smoke_test.py scripts
# Test tools that bootstrap-lowest installs, at the versions in requirements_dev.txt.
TEST_TOOLS := moto pylint pytest pytest-cov pytest-timeout

PWD := $(shell pwd)
ARCH := $(shell uname -m)

help:
	@python -c "$$PRINT_HELP_PYSCRIPT" < $(MAKEFILE_LIST)


.PHONY: pip
pip:
	pip install -U "pip ~= 26.1"

.PHONY: pip-tools
pip-tools: pip
	pip install -U "pip-tools ~= 6.6"

.PHONY: setuptools
setuptools: pip
	pip install -U "setuptools ~= 80.9.0"

.PHONY: hooks
hooks:
	mkdir -p .git/hooks
	test -f .git/hooks/pre-commit || cp hooks/pre-commit .git/hooks/pre-commit
	chmod 755 .git/hooks/pre-commit

.PHONY: bootstrap
bootstrap: hooks pip setuptools ## bootstrap the development environment
	pip install -r requirements.txt -r requirements_dev.txt
	pip install --editable .

.PHONY: bootstrap-lowest
bootstrap-lowest: ## install the lowest allowed versions of the direct dependencies, and the test tools (needs uv)
	uv pip install --resolution lowest-direct -r requirements.txt
	@# The test tools must not lift a dependency above the version just installed, so it's a constraint.
	mkdir -p build
	uv pip freeze > build/lowest-installed.txt
	for tool in $(TEST_TOOLS); do grep -E "^$$tool " requirements_dev.txt; done > build/lowest-test-tools.txt
	uv pip install -r build/lowest-test-tools.txt --constraint build/lowest-installed.txt
	uv pip install --no-deps --editable .
	uv pip check
	uv pip freeze


.PHONY: install-infrahouse-repo
install-infrahouse-repo:
	# Install dependencies
	apt-get update
	apt-get install gpg lsb-release curl
	# Add a GPG public key to verify InfraHouse packages
	mkdir -p /etc/apt/cloud-init.gpg.d/
	curl  -fsSL https://release-$$(lsb_release -cs).infrahouse.com/DEB-GPG-KEY-release-$$(lsb_release -cs).infrahouse.com \
		| gpg --dearmor -o /etc/apt/cloud-init.gpg.d/infrahouse.gpg
	# Add the InfraHouse repository source
	echo "deb [signed-by=/etc/apt/cloud-init.gpg.d/infrahouse.gpg] https://release-$$(lsb_release -cs).infrahouse.com/ $$(lsb_release -cs) main" \
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
	black infrahouse_toolkit $(TOOLING_PY)

.PHONY: isort
isort: ## reformat imports
	isort infrahouse_toolkit $(TOOLING_PY)

.PHONY: reqsort
reqsort: ## sort requirements files
	for f in requirements.txt requirements_dev.txt; do tmp_file=$$(tempfile) && sort -f $$f > "$$tmp_file" && mv "$$tmp_file" $$f; done

.PHONY: mdformat
mdformat: ## format markdown files
	mdformat .github

.PHONY: lint
lint: lint/yaml lint/black lint/isort lint/mdformat lint/reqsort lint/pylint lint/pylint-disables ## check style

.PHONY: lint/yaml
lint/yaml: ## check style with yamllint
	yamllint infrahouse_toolkit .github .readthedocs.yaml packaging

.PHONY: lint/black
lint/black: ## check style with black
	black --check --diff infrahouse_toolkit $(TOOLING_PY)

.PHONY: lint/isort
lint/isort: ## check imports formatting
	isort --check-only infrahouse_toolkit $(TOOLING_PY)

.PHONY: lint/mdformat
lint/mdformat:
	mdformat --check .github

.PHONY: lint/reqsort
lint/reqsort: ## check requirements sorting order
	@set -e ; for f in requirements.txt requirements_dev.txt; do test "$$(sort -f $$f)" = "$$(cat $$f)" || (echo "$$f is not sorted, run make reqsort" ; exit 1); done

.PHONY: lint/pylint
lint/pylint: ## check style with pylint
	pylint infrahouse_toolkit $(TOOLING_PY)

.PHONY: lint/pylint-disables
lint/pylint-disables: ## fail on pylint suppressions that hide calls not matching a function's signature
	python scripts/check_pylint_disables.py


.PHONY: test
test: ## run tests quickly with the default Python
	set
	pytest --cov \
		--cov-report=term-missing --cov-report=xml  \
		-xvvs infrahouse_toolkit scripts

.PHONY: tox
tox: ## run tests across Python 3.11 - 3.14 with tox
	tox

.PHONY: docs
docs: ## generate Sphinx HTML documentation, including API docs
	sphinx-apidoc -o docs/ infrahouse_toolkit
	$(MAKE) -C docs clean
	$(MAKE) -C docs html
	$(BROWSER) docs/_build/html/index.html

.PHONY: release
release: dist ## Build a Python packager and upload a release to PyPI
	twine upload dist/*

# Internal function to handle version release
# Args: $(1) = major|minor|patch
define do_release
	@echo "Checking if bumpversion is installed..."
	@command -v bump2version >/dev/null 2>&1 || { \
		echo ""; \
		echo "Error: bump2version is not installed."; \
		echo ""; \
		echo "Please install it using:"; \
		echo "  make bootstrap"; \
		echo ""; \
		exit 1; \
	}
	@BRANCH=$$(git rev-parse --abbrev-ref HEAD); \
	if [ "$$BRANCH" != "main" ]; then \
		echo "Error: You must be on the 'main' branch to release."; \
		echo "Current branch: $$BRANCH"; \
		exit 1; \
	fi; \
	CURRENT=$$(grep ^current_version setup.cfg | head -1 | cut -d= -f2 | tr -d ' '); \
	echo "Current version: $$CURRENT"; \
	MAJOR=$$(echo $$CURRENT | cut -d. -f1); \
	MINOR=$$(echo $$CURRENT | cut -d. -f2); \
	PATCH=$$(echo $$CURRENT | cut -d. -f3); \
	if [ "$(1)" = "major" ]; then \
		NEW_VERSION=$$((MAJOR + 1)).0.0; \
	elif [ "$(1)" = "minor" ]; then \
		NEW_VERSION=$$MAJOR.$$((MINOR + 1)).0; \
	elif [ "$(1)" = "patch" ]; then \
		NEW_VERSION=$$MAJOR.$$MINOR.$$((PATCH + 1)); \
	fi; \
	echo "New version will be: $$NEW_VERSION"; \
	printf "Continue? (y/n) "; \
	read -r REPLY; \
	case "$$REPLY" in \
		[Yy]|[Yy][Ee][Ss]) \
			echo "Bumping version with bump2version..."; \
			bump2version --new-version $$NEW_VERSION $(1); \
			echo ""; \
			echo "Released version $$NEW_VERSION"; \
			echo ""; \
			echo "Next steps:"; \
			echo "  git push && git push --tags"; \
			;; \
		*) \
			echo "Release cancelled"; \
			;; \
	esac
endef

.PHONY: release-patch
release-patch: ## Release a patch version (x.x.PATCH)
	$(call do_release,patch)

.PHONY: release-minor
release-minor: ## Release a minor version (x.MINOR.0)
	$(call do_release,minor)

.PHONY: release-major
release-major: ## Release a major version (MAJOR.0.0)
	$(call do_release,major)


.PHONY: package
package:
	docker run \
	-v ${PWD}:/infrahouse-toolkit \
	--name infrahouse-toolkit-builder \
	--rm \
	"twindb/omnibus-ubuntu:${OS_VERSION}-${ARCH}" \
	bash -l /infrahouse-toolkit/omnibus-infrahouse-toolkit/omnibus_build.sh

# uv keeps the versions already pinned in requirements.lock while they satisfy requirements.txt,
# so this changes the lock only when requirements.txt does. CI fails when it would.
.PHONY: lock
lock: ## Regenerate requirements.lock from requirements.txt
	uv pip compile --universal --python-version 3.10 --generate-hashes --quiet requirements.txt -o requirements.lock

# The standalone package is built and tested for the host's architecture. The platform is explicit,
# so a cached image of another architecture is never used.
STANDALONE_PLATFORM := linux/$(subst x86_64,amd64,$(subst aarch64,arm64,$(ARCH)))

# -e PACKAGE_VERSION_SUFFIX passes the suffix into the container only when it is set; see packaging/build.sh.
.PHONY: package-standalone
package-standalone: ## Build a self-contained Debian package (python-build-standalone + nfpm) into dist/
	docker build --platform $(STANDALONE_PLATFORM) -t infrahouse-toolkit-packager packaging
	docker run --platform $(STANDALONE_PLATFORM) --rm -e PACKAGE_VERSION_SUFFIX \
		-v $(PWD):/infrahouse-toolkit infrahouse-toolkit-packager

# apt-get installs the package's dependencies too, so this also proves they resolve on that release.
.PHONY: package-smoke-test
package-smoke-test: ## Install the package from dist/ on a clean Ubuntu (STANDALONE_OS_VERSION) and smoke-test it
	docker run --platform $(STANDALONE_PLATFORM) --pull always --rm -v $(PWD):/src -w /src \
		ubuntu:$(STANDALONE_OS_VERSION) bash -ec '\
		export DEBIAN_FRONTEND=noninteractive; \
		apt-get -qq update; \
		apt-get -qq install -y --no-install-recommends ./dist/infrahouse-toolkit_*.deb; \
		/opt/infrahouse-toolkit/embedded/bin/python3 -I packaging/smoke_test.py'

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

.PHONY: install
install: ## Install infrahouse-toolkit to the embedded Python
	/opt/infrahouse-toolkit/embedded/bin/pip3 install .

.PHONY: venv
venv: ## Create local python virtual environment
	python3 -m venv .venv
	@echo "To activate run"
	@echo ""
	@echo ". .venv/bin/activate"
