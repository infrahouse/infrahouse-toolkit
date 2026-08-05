"""
Unit tests for :py:mod:`infrahouse_toolkit.osv.scan_report`.

osv-scanner reports a CVSS score per group of aliases rather than per record,
so a record without its own severity rating gets the score of its group.
"""

import json
from unittest import mock

import pytest

from infrahouse_toolkit.osv import SEVERITY_UNKNOWN
from infrahouse_toolkit.osv.scan_report import ScanReport


@pytest.fixture(name="popen")
def _popen():
    """Patch Popen so that osv-scanner isn't actually executed."""

    def _mock(stdout, stderr=b""):
        proc = mock.MagicMock()
        proc.communicate.return_value = (stdout, stderr)
        popen = mock.MagicMock()
        popen.return_value.__enter__.return_value = proc
        return popen

    return _mock


def test_vulnerabilities(popen, aiohttp_report):
    """Every OSV record of every package makes it into the report."""
    with mock.patch("infrahouse_toolkit.osv.scan_report.Popen", popen(aiohttp_report)):
        vulnerabilities = ScanReport().vulnerabilities

    assert [(vuln.id, vuln.severity) for vuln in vulnerabilities] == [
        ("PYSEC-2026-3545", "HIGH"),
        ("GHSA-cq5v-8q36-5273", "HIGH"),
        ("PYSEC-2026-3546", "MEDIUM"),
        ("GHSA-mfx4-hv73-q22v", "MODERATE"),
    ]
    assert all(str(vuln.package) == "aiohttp==3.14.1" for vuln in vulnerabilities)


def test_score_comes_from_the_group_of_aliases(popen, aiohttp_report):
    """A PYSEC record borrows the score osv-scanner calculated for its group."""
    with mock.patch("infrahouse_toolkit.osv.scan_report.Popen", popen(aiohttp_report)):
        scores = {vuln.id: vuln.score for vuln in ScanReport().vulnerabilities}

    assert scores == {
        "PYSEC-2026-3545": 7.1,
        "GHSA-cq5v-8q36-5273": 7.1,
        "PYSEC-2026-3546": 6.3,
        "GHSA-mfx4-hv73-q22v": 6.3,
    }


def test_package_without_vulnerabilities(popen, clean_package_report):
    """A package with no vulnerabilities has neither a vulnerabilities nor a groups key."""
    with mock.patch("infrahouse_toolkit.osv.scan_report.Popen", popen(clean_package_report)):
        assert ScanReport().vulnerabilities == []


def test_empty_report(popen):
    """osv-scanner found nothing to scan."""
    with mock.patch("infrahouse_toolkit.osv.scan_report.Popen", popen(json.dumps({"results": []}).encode())):
        assert ScanReport().vulnerabilities == []


def test_report_without_groups(popen):
    """Vulnerabilities are still reported when osv-scanner didn't calculate a score."""
    report = {
        "results": [
            {
                "packages": [
                    {
                        "package": {"name": "aiohttp", "version": "3.14.1", "ecosystem": "PyPI"},
                        "vulnerabilities": [{"id": "PYSEC-2026-3545"}],
                    }
                ]
            }
        ]
    }
    with mock.patch("infrahouse_toolkit.osv.scan_report.Popen", popen(json.dumps(report).encode())):
        vulnerabilities = ScanReport().vulnerabilities

    assert len(vulnerabilities) == 1
    assert vulnerabilities[0].severity == SEVERITY_UNKNOWN


def test_scan_command(popen, aiohttp_report, tmp_path):
    """The configuration file is passed to osv-scanner only when it exists."""
    config_file = tmp_path / "osv-scanner.toml"
    config_file.write_text("[[IgnoredVulns]]\n", encoding="utf-8")

    popen_mock = popen(aiohttp_report)
    with mock.patch("infrahouse_toolkit.osv.scan_report.Popen", popen_mock):
        assert ScanReport(config_file=str(config_file), extra_args=["--experimental-only-packages"]).vulnerabilities

    cmd = popen_mock.call_args[0][0]
    assert cmd[:2] == ["osv-scanner", "scan"]
    assert cmd[-4:] == ["--config", str(config_file), "--experimental-only-packages", "./"]


def test_scan_command_without_config(popen, aiohttp_report, tmp_path):
    """A missing configuration file isn't passed to osv-scanner."""
    popen_mock = popen(aiohttp_report)
    with mock.patch("infrahouse_toolkit.osv.scan_report.Popen", popen_mock):
        assert ScanReport(config_file=str(tmp_path / "missing.toml")).vulnerabilities

    assert "--config" not in popen_mock.call_args[0][0]


def test_report_is_scanned_once(popen, aiohttp_report):
    """The scan is expensive, so its result is remembered."""
    popen_mock = popen(aiohttp_report)
    with mock.patch("infrahouse_toolkit.osv.scan_report.Popen", popen_mock):
        report = ScanReport()
        assert report.vulnerabilities
        assert report.vulnerabilities

    popen_mock.assert_called_once()
