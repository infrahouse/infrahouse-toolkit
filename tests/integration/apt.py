"""
The apt side of the integration test: a repository's ``Packages`` index, and ``apt-cache policy`` on the instance.
"""

import re
from typing import Dict, List, Optional

import requests
from debian.deb822 import Packages
from debian.debian_support import Version

PACKAGE = "infrahouse-toolkit"

TESTING_REPO_URL = "https://testing-noble.infrahouse.com/"
TESTING_REPO_CODENAME = "noble-testing"
"""The testing repository CD publishes every candidate to (packaging/README.md, "Testing repository")."""

PACKAGES_INDEX_TIMEOUT = 30
"""Seconds to wait for the ``Packages`` index."""


class PackagesIndex:
    """
    The ``Packages`` index of one architecture of an apt repository, as apt reads it.

    :param repo_url: Repository URL, with a trailing slash.
    :type repo_url: str
    :param codename: Distribution codename, for example ``noble-testing``.
    :type codename: str
    :param architecture: Debian architecture, for example ``amd64``.
    :type architecture: str
    :param component: Repository component.
    :type component: str
    """

    def __init__(self, repo_url: str, codename: str, architecture: str, component: str = "main"):
        self._url = f"{repo_url}dists/{codename}/{component}/binary-{architecture}/Packages"
        self._paragraphs_cache: Optional[List[Packages]] = None

    # --- Public properties ---

    @property
    def url(self) -> str:
        """
        :return: URL of the ``Packages`` index.
        """
        return self._url

    # --- Public methods ---

    def newest(self, package: str) -> str:
        """
        The highest version of a package in the index, in Debian version order.

        :param package: Package name.
        :type package: str
        :return: The version, for example ``2.68.3+candidate.259.1-1``.
        :raise LookupError: If the index doesn't list the package.
        """
        versions = self.versions(package)
        if not versions:
            raise LookupError(f"{self._url} lists no {package}.")
        return max(versions, key=Version)

    def require(self, package: str, version: str) -> str:
        """
        Check that the index lists a version of a package.

        :param package: Package name.
        :type package: str
        :param version: Debian version, with its revision, for example ``2.68.3+candidate.259.1-1``.
        :type version: str
        :return: The version.
        :raise LookupError: If the index doesn't list that version.
        """
        versions = self.versions(package)
        if version not in versions:
            raise LookupError(
                f"{self._url} doesn't list {package} {version}. It lists: {', '.join(versions) or 'nothing'}."
            )
        return version

    def versions(self, package: str) -> List[str]:
        """
        Every version of a package in the index.

        :param package: Package name.
        :type package: str
        :return: Versions in the order of the index.
        """
        return [paragraph["Version"] for paragraph in self._paragraphs if paragraph["Package"] == package]

    # --- Private properties ---

    @property
    def _paragraphs(self) -> List[Packages]:
        if self._paragraphs_cache is None:
            response = requests.get(self._url, timeout=PACKAGES_INDEX_TIMEOUT)
            response.raise_for_status()
            self._paragraphs_cache = list(Packages.iter_paragraphs(response.text.splitlines(), use_apt_pkg=False))
        return self._paragraphs_cache


class AptPolicy:
    """
    The output of ``apt-cache policy <package>``: the installed version, and where each version comes from.

    A version table looks like this::

        Version table:
     *** 2.68.3+candidate.259.1-1 1001
            500 https://testing-noble.infrahouse.com noble-testing/main amd64 Packages
            100 /var/lib/dpkg/status
         2.68.3-1 500
            500 https://release-noble.infrahouse.com noble/main amd64 Packages

    :param text: The command's standard output.
    :type text: str
    """

    _INSTALLED_LINE = re.compile(r"^\s*Installed:\s*(\S+)\s*$", re.MULTILINE)
    _VERSION_LINE = re.compile(r"^ (?:\*\*\*| {3}) (\S+) -?\d+\s*$")
    _ORIGIN_LINE = re.compile(r"^\s{6,}-?\d+ (\S.*?)\s*$")

    def __init__(self, text: str):
        self._text = text

    def __str__(self) -> str:
        return self._text

    # --- Public properties ---

    @property
    def installed(self) -> Optional[str]:
        """
        :return: The installed version, or ``None`` if apt shows none (``(none)``) or the output has no such line.
        """
        match = self._INSTALLED_LINE.search(self._text)
        if match is None or match.group(1) == "(none)":
            return None
        return match.group(1)

    # --- Public methods ---

    def origins(self, version: str) -> List[str]:
        """
        Where apt finds a version: one line per source, without its priority.

        :param version: Debian version.
        :type version: str
        :return: For example ``["https://testing-noble.infrahouse.com noble-testing/main amd64 Packages",
            "/var/lib/dpkg/status"]``. Empty if the table doesn't list the version.
        """
        return self._version_table.get(version, [])

    # --- Private properties ---

    @property
    def _version_table(self) -> Dict[str, List[str]]:
        table: Dict[str, List[str]] = {}
        current = None
        for line in self._text.splitlines():
            version_match = self._VERSION_LINE.match(line)
            if version_match:
                current = version_match.group(1)
                table[current] = []
                continue
            origin_match = self._ORIGIN_LINE.match(line)
            if origin_match and current is not None:
                table[current].append(origin_match.group(1))
        return table
