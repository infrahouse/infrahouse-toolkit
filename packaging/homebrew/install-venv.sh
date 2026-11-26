#!/usr/bin/env bash
# Makes the virtualenv that mint_token.py runs in, at $1: infrahouse-core 1.4 and its dependencies from
# requirements.lock here, every file checked against its hash, wheels only, nothing resolved at install time.
# publish-homebrew (python-CD.yml) and its CI check (python-CI.yml) both use it. It's apart from the toolkit's own
# environment: the toolkit package pins an older infrahouse-core (requirements.txt), and this lock is no part of it.
set -euo pipefail

venv="${1:?usage: install-venv.sh <directory>}"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# The lock is compiled for Python 3.12 and later (make lock), the python3 of ubuntu-24.04.
if ! python3 -I -c 'import sys; sys.exit(sys.version_info < (3, 12))'; then
    version="$(python3 -I -c 'import platform; print(platform.python_version())')"
    echo "::error::$(command -v python3) is Python ${version}. requirements.lock needs 3.12 or later."
    exit 1
fi

python3 -m venv "${venv}"
"${venv}/bin/python" -I -m pip install --quiet --disable-pip-version-check --no-input \
    --require-hashes --no-deps --only-binary :all: -r "${here}/requirements.lock"
"${venv}/bin/python" -I -m pip check
"${venv}/bin/python" -I -c "from infrahouse_core.github import GitHubAppTokenSource, KMSSigner"
"${venv}/bin/python" -I -c "import sys; from importlib.metadata import version as v
print('Python', sys.version.split()[0], '/ infrahouse-core', v('infrahouse-core'), '/ PyGithub', v('PyGithub'))"
