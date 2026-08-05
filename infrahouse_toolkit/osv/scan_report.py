"""
Module for ScanReport class - a vulnerability report produced by osv-scanner.
"""

import json
from functools import cached_property
from logging import getLogger
from os import path as osp
from subprocess import PIPE, Popen
from typing import List, Optional

from infrahouse_toolkit.osv.package import Package
from infrahouse_toolkit.osv.vulnerability import Vulnerability

LOG = getLogger()


class ScanReport:  # pylint: disable=too-few-public-methods
    """
    A vulnerability report osv-scanner produces for a directory.

    The scan runs on the first access to the report and its result is remembered.

    :param path: Directory to scan.
    :type path: str
    :param config_file: Path to an osv-scanner configuration file.
        The option is passed to osv-scanner only if the file exists.
    :type config_file: str
    :param extra_args: Extra arguments to pass to osv-scanner.
    :type extra_args: list
    """

    def __init__(self, path: str = "./", config_file: Optional[str] = None, extra_args: Optional[List[str]] = None):
        self._path = path
        self._config_file = config_file
        self._extra_args = extra_args or []

    @property
    def vulnerabilities(self) -> List[Vulnerability]:
        """
        :return: Vulnerabilities osv-scanner found in all scanned packages.
        :rtype: list
        """
        vulnerabilities = []
        for result in self._report.get("results", []):
            for package_item in result.get("packages", []):
                package = Package(package_item.get("package", {}))
                cvss_scores = self._cvss_scores(package_item)
                for record in package_item.get("vulnerabilities", []):
                    vulnerabilities.append(
                        Vulnerability(record, package=package, cvss_score=cvss_scores.get(record["id"]))
                    )

        return vulnerabilities

    @cached_property
    def _report(self) -> dict:
        """
        :return: The osv-scanner JSON report.
        :rtype: dict
        """
        cmd = ["osv-scanner", "scan", "--format", "json", "--recursive", "--verbosity", "warn"]
        config_file = self._config_file
        if config_file and osp.exists(config_file):
            cmd.extend(["--config", config_file])
        cmd.extend(self._extra_args)
        cmd.append(self._path)
        with Popen(cmd, stderr=PIPE, stdout=PIPE) as proc:
            LOG.debug("Launched command: %s", " ".join(cmd))
            cout, cerr = proc.communicate()
            if cerr:
                LOG.error(cerr.decode())

            return json.loads(cout)

    @staticmethod
    def _cvss_scores(package_item: dict) -> dict:
        """
        Map every vulnerability identifier of a package to its CVSS score.

        osv-scanner calculates the score per group of aliases - a CVE and its PYSEC
        and GHSA records belong to one group - so any identifier of a group
        resolves to the score of the group.

        :param package_item: A package entry of the osv-scanner JSON report.
        :type package_item: dict
        :return: Vulnerability identifiers mapped to CVSS scores,
            e.g. ``{"PYSEC-2026-3545": "7.1"}``.
        :rtype: dict
        """
        return {
            vuln_id: group.get("max_severity")
            for group in package_item.get("groups", [])
            for vuln_id in group.get("ids", [])
        }
