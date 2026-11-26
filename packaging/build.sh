#!/usr/bin/env bash
#
# Build a self-contained infrahouse-toolkit Debian package.
#
#   * Interpreter: a prebuilt python-build-standalone CPython, fetched by uv.
#   * Dependencies: installed from requirements.lock (hash-pinned).
#   * Package: assembled by nfpm from packaging/nfpm.yaml.
#
# The toolkit is installed at its final path, /opt/infrahouse-toolkit, so entry-point
# shebangs need no rewriting. Run it in a disposable container (see `make package-standalone`),
# never on a workstation: it writes to /opt and /usr/local/bin.
#
# packaging/build-macos.sh is its macOS twin: the tarball for the Homebrew formula, from the same interpreter,
# uv version and requirements.lock. A change to one of them likely belongs in the other.
#
# Environment:
#   PYTHON_VERSION   CPython version to embed (default 3.13)
#   GLIBC_FLOOR      Oldest glibc the package must run on, as manylinux tag digits (default 2_35,
#                    Ubuntu jammy). Wheels are chosen for this floor, not for the build host.
#   OUTPUT_DIR       Where to write the .deb (default ./dist)
#   PACKAGE_VERSION_SUFFIX
#                    Appended to the toolkit version in the package version: +candidate.214.1 builds
#                    2.67.0+candidate.214.1-1, which sorts above 2.67.0-1 and below 2.67.1-1.
#                    A + followed by letters, digits and dots. Empty by default: the plain toolkit
#                    version. CD sets it for candidates on the testing repo (packaging/README.md).
#                    The toolkit's own __version__ doesn't change.

set -euo pipefail

PYTHON_VERSION="${PYTHON_VERSION:-3.13}"
GLIBC_FLOOR="${GLIBC_FLOOR:-2_35}"
OUTPUT_DIR="${OUTPUT_DIR:-dist}"
PACKAGE_VERSION_SUFFIX="${PACKAGE_VERSION_SUFFIX:-}"
INSTALL_DIR="/opt/infrahouse-toolkit"
EMBEDDED="${INSTALL_DIR}/embedded"

# Checked before the build, so a bad suffix fails in seconds, not after it.
SUFFIX_PATTERN='^\+[A-Za-z0-9.]+$'
if [[ -n "${PACKAGE_VERSION_SUFFIX}" && ! "${PACKAGE_VERSION_SUFFIX}" =~ ${SUFFIX_PATTERN} ]]; then
    echo "PACKAGE_VERSION_SUFFIX must be a + followed by letters, digits and dots, got '${PACKAGE_VERSION_SUFFIX}'" >&2
    exit 1
fi

cd "$(dirname "$0")/.."
REPO_ROOT="$(pwd)"

for tool in uv nfpm; do
    command -v "$tool" >/dev/null || { echo "$tool is required" >&2; exit 1; }
done

if [[ -e "${INSTALL_DIR}" ]]; then
    echo "${INSTALL_DIR} already exists; build in a clean container" >&2
    exit 1
fi

WORK_DIR="$(mktemp -d)"
trap 'rm -rf "${WORK_DIR}"' EXIT

echo "==> Fetching CPython ${PYTHON_VERSION} (python-build-standalone)"
UV_PYTHON_INSTALL_DIR="${WORK_DIR}/python" uv python install --no-bin "${PYTHON_VERSION}"
PYTHON_SRC="$(find "${WORK_DIR}/python" -mindepth 1 -maxdepth 1 -type d -name 'cpython-*' | head -1)"
mkdir -p "${INSTALL_DIR}"
cp -a "${PYTHON_SRC}" "${EMBEDDED}"
# uv marks its managed interpreters as externally managed; this one is ours to manage.
find "${EMBEDDED}/lib" -maxdepth 2 -name EXTERNALLY-MANAGED -delete

PYTHON="${EMBEDDED}/bin/python3"
# The interpreter build, for comparing with the macOS tarball's (build-macos.sh prints the same).
"${PYTHON}" -VV
echo "python-build-standalone $(cat "${EMBEDDED}/BUILD")"
# Precompile the standard library so the interpreter never writes bytecode at runtime,
# which would leave files behind on package removal.
"${PYTHON}" -m compileall -q -j 0 "${EMBEDDED}/lib" >/dev/null
TARGET_PLATFORM="$(uname -m)-manylinux_${GLIBC_FLOOR}"

echo "==> Installing locked dependencies for ${TARGET_PLATFORM}"
uv pip install \
    --python "${PYTHON}" \
    --python-platform "${TARGET_PLATFORM}" \
    --require-hashes \
    --no-deps \
    --compile-bytecode \
    -r requirements.lock

echo "==> Installing infrahouse-toolkit"
# Build with the embedded interpreter. Without --python, uv finds no Python in the container
# and downloads its newest one just to run the build backend.
uv build --python "${PYTHON}" --wheel --out-dir "${WORK_DIR}/wheel" .
uv pip install --python "${PYTHON}" --no-deps --compile-bytecode "${WORK_DIR}"/wheel/*.whl

echo "==> Checking installed dependencies are consistent"
uv pip check --python "${PYTHON}"

echo "==> Checking no binary needs a glibc newer than ${GLIBC_FLOOR//_/.}"
NEWEST_GLIBC="$(find "${INSTALL_DIR}" -type f -name '*.so*' -exec objdump -T {} + 2>/dev/null \
    | grep -oE 'GLIBC_[0-9]+\.[0-9]+' | sed 's/GLIBC_//' | sort -uV | tail -1)"
if [[ "$(printf '%s\n' "${NEWEST_GLIBC}" "${GLIBC_FLOOR//_/.}" | sort -V | tail -1)" != "${GLIBC_FLOOR//_/.}" ]]; then
    echo "A bundled library needs glibc ${NEWEST_GLIBC}, above the ${GLIBC_FLOOR//_/.} floor" >&2
    exit 1
fi

echo "==> Generating bash completion"
STAGE_DIR="packaging/.stage"
rm -rf "${STAGE_DIR}"
mkdir -p "${STAGE_DIR}/etc/bash_completion.d"
"${PYTHON}" omnibus-infrahouse-toolkit/update_bash_completion.py >/dev/null
mv /tmp/infrahouse-completion "${STAGE_DIR}/etc/bash_completion.d/infrahouse-completion"

echo "==> Building the Debian package"
VERSION="$("${PYTHON}" -c 'import infrahouse_toolkit; print(infrahouse_toolkit.__version__)')${PACKAGE_VERSION_SUFFIX}"
ARCH="$(dpkg --print-architecture)"
mkdir -p "${OUTPUT_DIR}"
VERSION="${VERSION}" ARCH="${ARCH}" \
    nfpm package --config packaging/nfpm.yaml --packager deb --target "${OUTPUT_DIR}/"

ls -l "${REPO_ROOT}/${OUTPUT_DIR}"/infrahouse-toolkit_*.deb
