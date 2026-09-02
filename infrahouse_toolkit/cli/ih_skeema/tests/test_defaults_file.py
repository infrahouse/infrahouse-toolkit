"""Tests for the MySQL defaults file written for Skeema's alter-wrapper."""

import os

import pytest

from infrahouse_toolkit.cli.ih_skeema.defaults_file import (
    mysql_defaults_file,
    quote_option_value,
)


@pytest.mark.parametrize(
    "value, expected",
    [
        ("simple", '"simple"'),
        # RDS permits these; each breaks an unquoted or unescaped option file.
        ("with,comma", '"with,comma"'),
        ("with#hash", '"with#hash"'),
        ("with space", '"with space"'),
        ("with$dollar", '"with$dollar"'),
        ("back\\slash", '"back\\\\slash"'),
        ("tab\\there", '"tab\\\\there"'),
        ("\\s\\b\\t", '"\\\\s\\\\b\\\\t"'),
    ],
)
def test_quote_option_value(value, expected):
    """Values are double-quoted and every backslash is doubled."""
    assert quote_option_value(value) == expected


def test_defaults_file_contents():
    """The file carries a [client] group with both credentials escaped."""
    with mysql_defaults_file("rds_admin", "pa,ss#word") as path:
        with open(path, encoding="utf-8") as handle:
            content = handle.read()

    assert content == '[client]\nuser="rds_admin"\npassword="pa,ss#word"\n'


def test_defaults_file_is_private():
    """A file holding a password must not be group or world readable."""
    with mysql_defaults_file("rds_admin", "secret") as path:
        assert os.stat(path).st_mode & 0o077 == 0


def test_defaults_file_is_removed():
    """The file does not outlive the context manager."""
    with mysql_defaults_file("rds_admin", "secret") as path:
        assert os.path.exists(path)

    assert not os.path.exists(path)


def test_defaults_file_removed_on_error():
    """An exception inside the block still removes the password from disk."""
    captured = None
    with pytest.raises(RuntimeError):
        with mysql_defaults_file("rds_admin", "secret") as path:
            captured = path
            raise RuntimeError("boom")

    assert not os.path.exists(captured)
