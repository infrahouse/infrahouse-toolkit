#!/usr/bin/env bash
#
# Build the self-contained infrahouse-toolkit tarball for macOS arm64, which the Homebrew formula installs.
# This is the macOS twin of build.sh, which builds the Debian package: the same python-build-standalone
# interpreter, fetched by the same uv version, the same requirements.lock and the same toolkit wheel.
#
#   * Interpreter: a prebuilt python-build-standalone CPython, fetched by uv. The uv version decides which build
#     and checksum that fetches, so it must be the version packaging/Dockerfile pins; the build checks it.
#   * Dependencies: installed from requirements.lock (hash-pinned) for aarch64-apple-darwin.
#   * Scripts: uv writes console scripts with an absolute path to the build tree. Their header is replaced with
#     packaging/macos-script-header, which runs the python3 next to the script's real path, so the tree works
#     wherever it is unpacked and through Homebrew's symlinks.
#   * Tarball: the tree itself is the root (bin/, lib/, ...), with no top-level directory; the formula installs it
#     with libexec.install Dir["*"]. Next to it, a .sha256 file in shasum -a 256 format.
#
# Run it natively on an arm64 Mac, with `make package-macos`; it needs no Docker. It builds in build/macos-arm64
# and leaves the tree there; `make package-macos-smoke-test` deletes it before it tests the tarball.
#
# Usage:
#   build-macos.sh                 Build dist/infrahouse-toolkit-<version>-macos-arm64.tar.gz and its .sha256.
#   build-macos.sh --uv-version    Print the uv version the build needs (packaging/Dockerfile's), for CI to install.
#
# Environment:
#   PYTHON_VERSION   CPython version to embed (default 3.13), as in build.sh
#   MACOS_FLOOR      Oldest macOS the tarball must run on (default 13.0, the first macOS with realpath(1), which
#                    the script header needs). Wheels are chosen for this floor, not for the build host, and the
#                    build fails if any Mach-O file in the tree needs a newer macOS.
#   OUTPUT_DIR       Where to write the tarball and its .sha256 (default ./dist). Earlier macOS tarballs there
#                    are removed, so it holds one.

set -euo pipefail

PYTHON_VERSION="${PYTHON_VERSION:-3.13}"
MACOS_FLOOR="${MACOS_FLOOR:-13.0}"
OUTPUT_DIR="${OUTPUT_DIR:-dist}"

cd "$(dirname "$0")/.."
# Physical paths throughout: uv writes this path into the scripts, and the check below searches for it.
REPO_ROOT="$(pwd -P)"
# make package-macos-smoke-test deletes this directory; keep in step with BUILD_DIR in smoke-test-macos.sh.
BUILD_DIR="${REPO_ROOT}/build/macos-arm64"
TREE="${BUILD_DIR}/tree"
SCRIPT_HEADER="${REPO_ROOT}/packaging/macos-script-header"

# packaging/Dockerfile is the one place that sets the uv version, for both builds.
UV_VERSION="$(sed -n 's|^COPY --from=ghcr.io/astral-sh/uv:\([0-9][0-9.]*\) .*|\1|p' packaging/Dockerfile)"
if [[ ! "${UV_VERSION}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "Can't read the uv version from packaging/Dockerfile, got '${UV_VERSION}'" >&2
    exit 1
fi
if [[ "${1:-}" == "--uv-version" ]]; then
    echo "${UV_VERSION}"
    exit 0
fi
if [[ $# -ne 0 ]]; then
    echo "Usage: $0 [--uv-version]" >&2
    exit 1
fi

# Checked before the build, so a bad floor fails in seconds, not after it.
if [[ ! "${MACOS_FLOOR}" =~ ^[0-9]+\.[0-9]+$ ]]; then
    echo "MACOS_FLOOR must be a macOS version such as 13.0, got '${MACOS_FLOOR}'" >&2
    exit 1
fi

if [[ "$(uname -s)" != "Darwin" || "$(uname -m)" != "arm64" ]]; then
    echo "This builds the macOS arm64 tarball natively; it runs only on an arm64 Mac, not $(uname -s) $(uname -m)" >&2
    exit 1
fi

for tool in uv otool file shasum tar; do
    command -v "$tool" >/dev/null || { echo "$tool is required" >&2; exit 1; }
done

INSTALLED_UV="$(uv --version | awk '{print $2}')"
if [[ "${INSTALLED_UV}" != "${UV_VERSION}" ]]; then
    echo "uv ${INSTALLED_UV} is on PATH, but packaging/Dockerfile pins uv ${UV_VERSION}, and the uv version decides" \
        "which python-build-standalone build the tarball gets. Install uv ${UV_VERSION}; see packaging/README.md." >&2
    exit 1
fi

rm -rf "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}" "${OUTPUT_DIR}"
OUTPUT_DIR="$(cd "${OUTPUT_DIR}" && pwd -P)"
# Before the build, so a failed build leaves no tarball for the smoke test to pick up.
rm -f "${OUTPUT_DIR}"/infrahouse-toolkit-*-macos-arm64.tar.gz "${OUTPUT_DIR}"/infrahouse-toolkit-*-macos-arm64.tar.gz.sha256

echo "==> Fetching CPython ${PYTHON_VERSION} (python-build-standalone) with uv ${UV_VERSION}"
UV_PYTHON_INSTALL_DIR="${BUILD_DIR}/python" uv python install --no-bin "${PYTHON_VERSION}"
PYTHON_SRC="$(find "${BUILD_DIR}/python" -mindepth 1 -maxdepth 1 -type d -name 'cpython-*' | head -1)"
mv "${PYTHON_SRC}" "${TREE}"
rm -rf "${BUILD_DIR}/python"
# uv marks its managed interpreters as externally managed; this one is ours to manage.
find "${TREE}/lib" -maxdepth 2 -name EXTERNALLY-MANAGED -delete

PYTHON="${TREE}/bin/python3"
# The interpreter build, for comparing with the Debian package's (build.sh prints the same).
"${PYTHON}" -VV
echo "python-build-standalone $(cat "${TREE}/BUILD")"
# Precompile the standard library, as build.sh does, so the interpreter doesn't write bytecode at runtime.
"${PYTHON}" -m compileall -q -j 0 "${TREE}/lib" >/dev/null

echo "==> Installing locked dependencies for aarch64-apple-darwin, macOS ${MACOS_FLOOR} and later"
# uv picks wheels for MACOSX_DEPLOYMENT_TARGET, not for the macOS it runs on.
MACOSX_DEPLOYMENT_TARGET="${MACOS_FLOOR}" uv pip install \
    --python "${PYTHON}" \
    --python-platform aarch64-apple-darwin \
    --require-hashes \
    --no-deps \
    --compile-bytecode \
    -r requirements.lock

echo "==> Installing infrahouse-toolkit"
# Build with the embedded interpreter, as build.sh does.
uv build --python "${PYTHON}" --wheel --out-dir "${BUILD_DIR}/wheel" .
uv pip install --python "${PYTHON}" --no-deps --compile-bytecode "${BUILD_DIR}"/wheel/*.whl

echo "==> Checking installed dependencies are consistent"
uv pip check --python "${PYTHON}"

echo "==> Making the console scripts relocatable"
# uv's scripts start with "#!<tree>/bin/python3", or, when that path is too long for a shebang or has a space,
# with a three-line /bin/sh header like ours that runs '<tree>/bin/python3'. Either is replaced with our header.
# Anything else is left alone: the interpreter itself, symlinks, and python-build-standalone's own scripts
# (pip, pydoc3, ...), which are relocatable already.
rewritten=0
for script in "${TREE}"/bin/*; do
    if [[ -L "${script}" || ! -f "${script}" || "$(head -c 2 "${script}")" != "#!" ]]; then
        continue
    fi
    line1="$(sed -n 1p "${script}")"
    line2="$(sed -n 2p "${script}")"
    line3="$(sed -n 3p "${script}")"
    if [[ "${line1}" == "#!${TREE}/"* ]]; then
        header_lines=1
    elif [[ "${line1}" == "#!/bin/sh" && "${line2}" == "'''exec' '${TREE}/"* && "${line3}" == "' '''" ]]; then
        header_lines=3
    else
        continue
    fi
    body="${BUILD_DIR}/script-body"
    tail -n +"$((header_lines + 1))" "${script}" > "${body}"
    # Rewritten in place, so the file keeps its mode.
    cat "${SCRIPT_HEADER}" "${body}" > "${script}"
    rm "${body}"
    rewritten=$((rewritten + 1))
done
echo "Rewrote the header of ${rewritten} scripts in bin/"
# grep exits 1 when nothing matches; anything else is an error.
LEFT="$(grep -l -F -- "${BUILD_DIR}" "${TREE}"/bin/* || [[ $? -eq 1 ]])"
if [[ -n "${LEFT}" ]]; then
    echo "These files in bin/ still contain the build directory, ${BUILD_DIR}:" >&2
    echo "${LEFT}" >&2
    exit 1
fi

echo "==> Checking no Mach-O file needs a macOS newer than ${MACOS_FLOOR}"
# file(1) prints one line per file, and for a universal binary one more per architecture, which are skipped.
find "${TREE}" -type f -exec file --no-pad --mime-type {} + > "${BUILD_DIR}/file-types"
sed -n '/ (for architecture /d; s|: application/x-mach-binary$||p' "${BUILD_DIR}/file-types" \
    > "${BUILD_DIR}/mach-o-files"
MACHO_COUNT="$(wc -l < "${BUILD_DIR}/mach-o-files" | tr -d ' ')"
if [[ "${MACHO_COUNT}" -eq 0 ]]; then
    echo "Found no Mach-O file in ${TREE}, not even the interpreter" >&2
    exit 1
fi
NEWEST_MINOS="0.0"
NEWEST_FILE=""
TOO_NEW=""
while IFS= read -r macho; do
    # minos of LC_BUILD_VERSION, or version of the older LC_VERSION_MIN_MACOSX, for every architecture in the file.
    minos="$(otool -l "${macho}" | awk '
        $2 == "LC_BUILD_VERSION" || $2 == "LC_VERSION_MIN_MACOSX" { want = 1; next }
        want && ($1 == "minos" || $1 == "version") { print $2; want = 0 }
    ' | sort -V | tail -1)"
    if [[ -z "${minos}" ]]; then
        echo "${macho#"${TREE}"/} has no minimum macOS version" >&2
        exit 1
    fi
    if [[ "$(printf '%s\n' "${minos}" "${NEWEST_MINOS}" | sort -V | tail -1)" == "${minos}" ]]; then
        NEWEST_MINOS="${minos}"
        NEWEST_FILE="${macho#"${TREE}"/}"
    fi
    if [[ "$(printf '%s\n' "${minos}" "${MACOS_FLOOR}" | sort -V | tail -1)" != "${MACOS_FLOOR}" ]]; then
        TOO_NEW="${TOO_NEW}  ${macho#"${TREE}"/} needs macOS ${minos}"$'\n'
    fi
done < "${BUILD_DIR}/mach-o-files"
echo "Checked ${MACHO_COUNT} Mach-O files. The newest minos is ${NEWEST_MINOS}, in ${NEWEST_FILE}."
if [[ -n "${TOO_NEW}" ]]; then
    echo "These files need a macOS newer than the ${MACOS_FLOOR} floor:" >&2
    printf '%s' "${TOO_NEW}" >&2
    exit 1
fi

VERSION="$("${PYTHON}" -I -c 'import infrahouse_toolkit; print(infrahouse_toolkit.__version__)')"
TARBALL="infrahouse-toolkit-${VERSION}-macos-arm64.tar.gz"

echo "==> Packing ${TARBALL}"
# The tree's top-level entries by name, so the archive holds bin/, lib/, ... and no ./ entry. No macOS metadata:
# COPYFILE_DISABLE=1 leaves out ._* files, --no-xattrs extended attributes such as com.apple.provenance.
(cd "${TREE}" && ls -A) > "${BUILD_DIR}/top-level"
COPYFILE_DISABLE=1 tar --no-mac-metadata --no-xattrs --no-acls \
    -czf "${OUTPUT_DIR}/${TARBALL}" -C "${TREE}" -T "${BUILD_DIR}/top-level"
tar -tzf "${OUTPUT_DIR}/${TARBALL}" > "${BUILD_DIR}/tarball-entries"
if grep -E '(^|/)(\._[^/]*|\.DS_Store)$' "${BUILD_DIR}/tarball-entries" >&2; then
    echo "The tarball has the macOS metadata files above" >&2
    exit 1
fi
(cd "${OUTPUT_DIR}" && shasum -a 256 "${TARBALL}" > "${TARBALL}.sha256")

echo "Tarball: $(wc -c < "${OUTPUT_DIR}/${TARBALL}" | tr -d ' ') bytes," \
    "$(grep -c -v '/$' "${BUILD_DIR}/tarball-entries") files and symlinks," \
    "$(du -sh "${TREE}" | cut -f1) unpacked"
cat "${OUTPUT_DIR}/${TARBALL}.sha256"
ls -l "${OUTPUT_DIR}/${TARBALL}" "${OUTPUT_DIR}/${TARBALL}.sha256"
