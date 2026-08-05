"""Fixtures with osv-scanner reports."""

import json

import pytest

# A trimmed down report osv-scanner 2.4.0 produced for a requirements.txt
# with aiohttp==3.14.1. Every vulnerability is described by two OSV records:
# one from the PyPI Advisory Database (PYSEC) and one from the GitHub Advisory
# Database (GHSA). Only the GHSA records have the "database_specific" section.
AIOHTTP_REPORT = {
    "results": [
        {
            "source": {"path": "/code/requirements.txt", "type": "lockfile"},
            "packages": [
                {
                    "package": {"name": "aiohttp", "version": "3.14.1", "ecosystem": "PyPI"},
                    "vulnerabilities": [
                        {
                            "id": "PYSEC-2026-3545",
                            "aliases": ["CVE-2026-69244", "GHSA-cq5v-8q36-5273"],
                            "severity": [
                                {
                                    "score": "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:P/VC:N/VI:N/VA:H/SC:N/SI:N/SA:N",
                                    "type": "CVSS_V4",
                                }
                            ],
                        },
                        {
                            "id": "GHSA-cq5v-8q36-5273",
                            "aliases": ["CVE-2026-69244"],
                            "database_specific": {"cwe_ids": ["CWE-125"], "severity": "HIGH"},
                        },
                        {
                            "id": "PYSEC-2026-3546",
                            "aliases": ["CVE-2026-69243", "GHSA-mfx4-hv73-q22v"],
                        },
                        {
                            "id": "GHSA-mfx4-hv73-q22v",
                            "aliases": ["CVE-2026-69243"],
                            "database_specific": {"cwe_ids": ["CWE-444"], "severity": "MODERATE"},
                        },
                    ],
                    "groups": [
                        {
                            "ids": ["PYSEC-2026-3545", "GHSA-cq5v-8q36-5273"],
                            "aliases": ["CVE-2026-69244", "GHSA-cq5v-8q36-5273", "PYSEC-2026-3545"],
                            "max_severity": "7.1",
                        },
                        {
                            "ids": ["PYSEC-2026-3546", "GHSA-mfx4-hv73-q22v"],
                            "aliases": ["CVE-2026-69243", "GHSA-mfx4-hv73-q22v", "PYSEC-2026-3546"],
                            "max_severity": "6.3",
                        },
                    ],
                }
            ],
        }
    ]
}

# osv-scanner omits the "vulnerabilities" and "groups" keys altogether
# for packages without vulnerabilities. Such packages show up in the report
# when the license scanning is enabled.
CLEAN_PACKAGE_REPORT = {
    "results": [
        {
            "source": {"path": "/code/requirements.txt", "type": "lockfile"},
            "packages": [
                {
                    "package": {"name": "certifi", "version": "2025.10.5", "ecosystem": "PyPI"},
                    "licenses": ["MPL-2.0"],
                    "license_violations": ["MPL-2.0"],
                }
            ],
        }
    ]
}


@pytest.fixture
def aiohttp_report():
    """
    :return: An osv-scanner report where the same vulnerabilities come
        from the PyPI and the GitHub advisory databases.
    :rtype: bytes
    """
    return json.dumps(AIOHTTP_REPORT).encode()


@pytest.fixture
def clean_package_report():
    """
    :return: An osv-scanner report with a package that has no vulnerabilities.
    :rtype: bytes
    """
    return json.dumps(CLEAN_PACKAGE_REPORT).encode()
