#!/usr/bin/env bash
# Checks the GitHub release v$VERSION's macOS tarball against its .sha256, and writes the checksum to
# $GITHUB_OUTPUT as sha256=<hash>. publish-homebrew (python-CD.yml) runs it before it mints a token: the formula
# gets the checksum of the file users download, never this run's build. It downloads from the url the formula
# gets, so a url that doesn't work fails here too.
#
# Environment: VERSION (X.Y.Z), GITHUB_OUTPUT (optional). RELEASE_DOWNLOAD_BASE replaces
# https://github.com/infrahouse/infrahouse-toolkit/releases/download for the tests (test.sh) only.
# See the "How a release reaches the Homebrew formula" section of packaging/README.md.
set -euo pipefail

: "${VERSION:?VERSION is the version of the release, X.Y.Z}"
if [[ ! "${VERSION}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "::error::VERSION is '${VERSION}', not X.Y.Z"
    exit 1
fi

base="${RELEASE_DOWNLOAD_BASE:-https://github.com/infrahouse/infrahouse-toolkit/releases/download}/v${VERSION}"
tarball="infrahouse-toolkit-${VERSION}-macos-arm64.tar.gz"
dir="$(mktemp -d)"
trap 'rm -rf "${dir}"' EXIT

for file in "${tarball}.sha256" "${tarball}"; do
    if ! curl --fail --silent --show-error --location --max-time 600 --retry 3 --retry-delay 5 \
            --output "${dir}/${file}" "${base}/${file}"; then
        echo "::error::Release v${VERSION} has no ${file} at ${base}/${file}. publish-macos attaches it:" \
            "check its run, then re-run the failed jobs."
        exit 1
    fi
done

# One line, as shasum -a 256 writes it, with the file name and no directory.
line_pattern='^([0-9a-f]{64})  (.+)$'
if [[ "$(wc -l < "${dir}/${tarball}.sha256")" -ne 1 \
      || ! "$(cat "${dir}/${tarball}.sha256")" =~ ${line_pattern} \
      || "${BASH_REMATCH[2]}" != "${tarball}" ]]; then
    echo "::error::The release's ${tarball}.sha256 isn't one line '<sha256>  ${tarball}'. It is:"
    cat "${dir}/${tarball}.sha256"
    exit 1
fi
expected="${BASH_REMATCH[1]}"

if command -v sha256sum > /dev/null; then
    actual="$(sha256sum "${dir}/${tarball}" | cut -d' ' -f1)"
else
    actual="$(shasum -a 256 "${dir}/${tarball}" | cut -d' ' -f1)"
fi
if [[ "${actual}" != "${expected}" ]]; then
    echo "::error::The release's ${tarball} has sha256 ${actual}, but its .sha256 says ${expected}." \
        "Users would download a file that doesn't match: check the release's assets (packaging/README.md)" \
        "before anything points the formula at it."
    exit 1
fi

echo "Release v${VERSION}: ${tarball} matches its .sha256, ${expected}"
if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
    echo "sha256=${expected}" >> "${GITHUB_OUTPUT}"
fi
