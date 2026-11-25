#!/usr/bin/env bash
#
# Smoke-test the macOS arm64 tarball in dist/ as Homebrew installs it (make package-macos-smoke-test):
#
#   1. Delete the build tree, build/macos-arm64, so nothing can resolve to it.
#   2. Check the .sha256, and unpack the tarball into a fresh directory whose path contains a space.
#   3. Link every ih-* script the way Homebrew does, through two relative symlinks in other directories:
#      links/ih-x -> keg/bin/ih-x -> <unpacked>/bin/ih-x.
#   4. With links/ first on a minimal PATH, run smoke_test.py --no-deb with the unpacked interpreter. It runs
#      every ih-* --help as a process, so each goes through both symlinks and the script header.
#   5. Import the native modules the formula's test imports.
#
# Runs on an arm64 Mac, after build-macos.sh.
#
# Environment:
#   OUTPUT_DIR       Where build-macos.sh wrote the tarball (default ./dist)

set -euo pipefail

OUTPUT_DIR="${OUTPUT_DIR:-dist}"

cd "$(dirname "$0")/.."
REPO_ROOT="$(pwd -P)"
# Where build-macos.sh builds the tree; keep in step with BUILD_DIR there.
BUILD_DIR="${REPO_ROOT}/build/macos-arm64"
SCRIPT_HEADER="${REPO_ROOT}/packaging/macos-script-header"

if [[ "$(uname -s)" != "Darwin" || "$(uname -m)" != "arm64" ]]; then
    echo "This tests the macOS arm64 tarball; it runs only on an arm64 Mac, not $(uname -s) $(uname -m)" >&2
    exit 1
fi

OUTPUT_DIR="$(cd "${OUTPUT_DIR}" && pwd -P)"
TARBALL="$(find "${OUTPUT_DIR}" -maxdepth 1 -name 'infrahouse-toolkit-*-macos-arm64.tar.gz')"
if [[ -z "${TARBALL}" || "${TARBALL}" == *$'\n'* ]]; then
    echo "Expected one infrahouse-toolkit-*-macos-arm64.tar.gz in ${OUTPUT_DIR}, found:" \
        "${TARBALL:-none}. Run make package-macos." >&2
    exit 1
fi
TARBALL_NAME="$(basename "${TARBALL}")"
VERSION="${TARBALL_NAME#infrahouse-toolkit-}"
VERSION="${VERSION%-macos-arm64.tar.gz}"

echo "==> Deleting the build tree, ${BUILD_DIR}"
rm -rf "${BUILD_DIR}"
if [[ -e "${BUILD_DIR}" ]]; then
    echo "${BUILD_DIR} still exists" >&2
    exit 1
fi

echo "==> Checking ${TARBALL_NAME}.sha256"
(cd "${OUTPUT_DIR}" && shasum -a 256 -c "${TARBALL_NAME}.sha256")

# Every path below contains a space.
SMOKE_ROOT="$(cd "$(mktemp -d)" && pwd -P)"
trap 'rm -rf "${SMOKE_ROOT}"' EXIT
WORK="${SMOKE_ROOT}/homebrew smoke test"
UNPACKED="${WORK}/libexec"
KEG_BIN="${WORK}/keg/bin"
LINKS="${WORK}/links"
mkdir -p "${UNPACKED}" "${KEG_BIN}" "${LINKS}"

echo "==> Unpacking into ${UNPACKED}"
tar -xzf "${TARBALL}" -C "${UNPACKED}"
for entry in bin/python3 lib; do
    if [[ ! -e "${UNPACKED}/${entry}" ]]; then
        echo "The tarball has no ${entry} at its root" >&2
        exit 1
    fi
done

echo "==> Linking the scripts: links/ih-x -> keg/bin/ih-x -> libexec/bin/ih-x"
SCRIPT_COUNT=0
for script in "${UNPACKED}"/bin/ih-*; do
    name="$(basename "${script}")"
    if [[ "$(head -n 3 "${script}")" != "$(cat "${SCRIPT_HEADER}")" ]]; then
        echo "${name} doesn't start with the header in packaging/macos-script-header:" >&2
        head -n 3 "${script}" >&2
        exit 1
    fi
    # Relative, as Homebrew links them: bin.install_symlink in the keg, then brew link into the prefix.
    ln -s "../../libexec/bin/${name}" "${KEG_BIN}/${name}"
    ln -s "../keg/bin/${name}" "${LINKS}/${name}"
    SCRIPT_COUNT=$((SCRIPT_COUNT + 1))
done
echo "Linked ${SCRIPT_COUNT} scripts"
# grep exits 1 when nothing matches; anything else is an error.
LEFT="$(grep -l -F -- "${BUILD_DIR}" "${UNPACKED}"/bin/* || [[ $? -eq 1 ]])"
if [[ -n "${LEFT}" ]]; then
    echo "These files in bin/ contain the build directory, ${BUILD_DIR}:" >&2
    echo "${LEFT}" >&2
    exit 1
fi

# Only the links and the system: no other Python, and no ih-* from an earlier install, can stand in.
export PATH="${LINKS}:/usr/bin:/bin:/usr/sbin:/sbin"
PYTHON="${UNPACKED}/bin/python3"

echo "==> Checking the scripts and the interpreter resolve to the unpacked tree"
for script in "${UNPACKED}"/bin/ih-*; do
    name="$(basename "${script}")"
    if [[ "$(command -v "${name}")" != "${LINKS}/${name}" ]]; then
        echo "${name} resolves to $(command -v "${name}"), not ${LINKS}/${name}" >&2
        exit 1
    fi
done
PREFIX="$("${PYTHON}" -I -c 'import sys; print(sys.prefix)')"
if [[ "${PREFIX}" != "${UNPACKED}" ]]; then
    echo "The unpacked interpreter's sys.prefix is ${PREFIX}, not ${UNPACKED}" >&2
    exit 1
fi
EC2_VERSION="$(ih-ec2 --version)"
echo "ih-ec2 --version: ${EC2_VERSION}"
if [[ "${EC2_VERSION}" != *"${VERSION}"* ]]; then
    echo "ih-ec2 --version doesn't print ${VERSION}, the tarball's version" >&2
    exit 1
fi

echo "==> Running smoke_test.py --no-deb"
"${PYTHON}" -I packaging/smoke_test.py --no-deb

echo "==> Importing the native modules"
"${PYTHON}" -I -c "import nacl.bindings, cryptography.hazmat.bindings._rust"
echo "nacl.bindings and cryptography.hazmat.bindings._rust import"
