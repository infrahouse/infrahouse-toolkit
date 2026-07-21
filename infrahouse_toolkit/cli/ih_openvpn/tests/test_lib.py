"""Unit tests for :py:mod:`infrahouse_toolkit.cli.ih_openvpn.lib`."""

import pytest

from infrahouse_toolkit.cli.ih_openvpn.lib import (
    extract_common_name,
    is_user_certificate,
    parse_index,
    valid_user_certificates,
)

SERVER_DN = (
    "/C=US/ST=California/L=San Francisco/O=InfraHouse Inc."
    "/OU=Security Organization/CN=server/emailAddress=security@infrahouse.com"
)
USER_DN = "/C=US/ST=California/O=InfraHouse Inc./CN=alice@infrahouse.com"


def write_index(tmp_path, rows):
    """Write an easy-rsa style index.txt and return its path."""
    index = tmp_path / "index.txt"
    index.write_text("".join(rows), encoding="utf-8")
    return str(index)


def valid_row(subject, serial="01"):
    """A tab-separated index.txt row for a live certificate."""
    return f"V\t300101000000Z\t\t{serial}\tunknown\t{subject}\n"


def revoked_row(subject, serial="02"):
    """A tab-separated index.txt row for a revoked certificate."""
    return f"R\t300101000000Z\t250101000000Z\t{serial}\tunknown\t{subject}\n"


@pytest.mark.parametrize(
    "subject, expected",
    [
        (SERVER_DN, "server"),
        (USER_DN, "alice@infrahouse.com"),
        ("/CN=bob@infrahouse.com", "bob@infrahouse.com"),
        ("/C=US/O=NoCommonName", None),
        ("", None),
    ],
)
def test_extract_common_name(subject, expected):
    """CN is found wherever it sits in the DN, and absence is reported as None."""
    assert extract_common_name(subject) == expected


@pytest.mark.parametrize(
    "common_name, expected",
    [
        ("alice@infrahouse.com", True),
        ("server", False),
        (None, False),
        ("", False),
    ],
)
def test_is_user_certificate(common_name, expected):
    """Only email-shaped common names count as directory users."""
    assert is_user_certificate(common_name) is expected


def test_parse_index_reads_all_rows(tmp_path):
    """Every well-formed row is parsed, with status and CN extracted."""
    index = write_index(tmp_path, [valid_row(SERVER_DN), valid_row(USER_DN, "02")])
    entries = parse_index(index)
    assert [(entry.status, entry.common_name) for entry in entries] == [
        ("V", "server"),
        ("V", "alice@infrahouse.com"),
    ]


def test_parse_index_skips_malformed_rows(tmp_path):
    """A truncated row is skipped rather than aborting the whole reconciliation."""
    index = write_index(tmp_path, [valid_row(USER_DN), "garbage\n", "\n"])
    assert [entry.common_name for entry in parse_index(index)] == ["alice@infrahouse.com"]


def test_valid_user_certificates_excludes_server(tmp_path):
    """
    The server's own certificate is never a revocation candidate.

    This is the guard against the catastrophic case: on a fresh deployment the
    only valid certificate is CN=server, so a reconciliation that considered it
    would compute it as belonging to no active user and revoke it, taking down
    the VPN for everyone.
    """
    index = write_index(tmp_path, [valid_row(SERVER_DN)])
    assert valid_user_certificates(index) == set()


def test_valid_user_certificates_excludes_revoked(tmp_path):
    """Already-revoked certificates are not candidates again."""
    index = write_index(tmp_path, [valid_row(USER_DN), revoked_row("/CN=bob@infrahouse.com")])
    assert valid_user_certificates(index) == {"alice@infrahouse.com"}


def test_valid_user_certificates_mixed(tmp_path):
    """A realistic index yields only the live user certificates."""
    index = write_index(
        tmp_path,
        [
            valid_row(SERVER_DN, "01"),
            valid_row(USER_DN, "02"),
            valid_row("/CN=bob@infrahouse.com", "03"),
            revoked_row("/CN=carol@infrahouse.com", "04"),
        ],
    )
    assert valid_user_certificates(index) == {"alice@infrahouse.com", "bob@infrahouse.com"}
