"""Unit tests for :py:mod:`infrahouse_toolkit.cli.ih_skeema.cmd_preflight`."""

from unittest import mock

import pytest
from click.testing import CliRunner
from pymysql.err import OperationalError

from infrahouse_toolkit.cli.ih_skeema import ih_skeema
from infrahouse_toolkit.skeema import Skeema, SkeemaDiff

ERRORS = "2026-09-16 11:52:45 [INFO]  Generating diff of db:3306 shop vs /work/shop/*.sql\n"
PENDING = SkeemaDiff("-- instance: db:3306\nUSE `shop`;\nALTER TABLE `small` ADD COLUMN `w` int;\n", ERRORS, 1, "/work")
REFUSED = SkeemaDiff("", ERRORS + "2026-09-16 11:52:45 [ERROR] # DROP TABLE `gone`\n", 2, "/work")


@pytest.fixture(name="server")
def _server():
    """Patch MySQLServer so that no database is queried, and pretend skeema is installed."""
    with mock.patch("infrahouse_toolkit.cli.ih_skeema.check_output", return_value=b"skeema version 1.11.1"):
        with mock.patch("infrahouse_toolkit.skeema.preflight.MySQLServer") as server_class:
            server = server_class.return_value
            server.threads_running = 3
            server.table_sizes.return_value = {("shop", "small"): 16384}
            server.leftovers.return_value = []
            yield server


def _preflight(args, diff):
    """
    Invoke ``ih-skeema preflight`` with ``Skeema.diff`` returning a fixed diff.

    :param args: Arguments after ``preflight``.
    :param diff: What ``Skeema.diff`` returns.
    :return: The click result.
    """
    with mock.patch.object(Skeema, "diff", return_value=diff):
        return CliRunner().invoke(ih_skeema, ["--password", "secret", "preflight"] + args)


def test_preflight(server, tmp_path):  # pylint: disable=unused-argument
    """The report goes to stdout, the digest to the file, and the exit code is skeema's."""
    digest_file = tmp_path / "digest"

    result = _preflight(["production", "--allow-unsafe", "--digest-file", str(digest_file)], PENDING)

    assert result.exit_code == 1, result.output
    assert result.output.startswith("## Skeema preflight: production\n")
    assert "| `db:3306` | `shop` | `small` | ALTER | 16.0 KiB | plain |" in result.output
    assert digest_file.read_text() == PENDING.digest + "\n"


def test_preflight_when_diff_fails(server, tmp_path):  # pylint: disable=unused-argument
    """The report is still printed, but there is no digest to approve."""
    digest_file = tmp_path / "digest"

    result = _preflight(["production", "--digest-file", str(digest_file)], REFUSED)

    assert result.exit_code == 2
    assert "**skeema diff failed with exit code 2, so a push would fail too.**" in result.output
    assert not digest_file.exists()


def test_preflight_when_server_unreachable(server):
    """A database error is an error, not a report with gaps."""
    type(server).threads_running = mock.PropertyMock(side_effect=OperationalError(2003, "Can't connect"))

    result = _preflight(["production"], PENDING)

    assert result.exit_code == 2
    assert "Can't connect" in result.output


def test_preflight_without_password(server):
    """Without a password from any source, the preflight stops before running skeema or querying a server."""
    result = CliRunner(env={"MYSQL_PWD": None}).invoke(ih_skeema, ["preflight", "production"])

    assert result.exit_code == 2
    assert "No password for database user root" in result.output
    server.leftovers.assert_not_called()


def test_preflight_help_without_password(server):  # pylint: disable=unused-argument
    """Reading the help doesn't need credentials."""
    result = CliRunner(env={"MYSQL_PWD": None}).invoke(ih_skeema, ["preflight", "--help"])

    assert result.exit_code == 0, result.output
    assert "Usage: ih-skeema preflight" in result.output


# skeema renders an alter-wrapper from a template, so a clause that spans lines in the .sql
# file, such as a partition clause, makes the `\!` command span lines too.
WRAPPED_MULTILINE = SkeemaDiff(
    "-- instance: db:3306\n"
    "USE `shop`;\n"
    "\\! /usr/bin/pt-online-schema-change --plugin /work/shop/../osc-guard.pm "
    "--alter '/*!50500 PARTITION BY RANGE  COLUMNS(created_at)\n"
    "(PARTITION pmax VALUES LESS THAN (MAXVALUE) ENGINE = InnoDB) */' "
    "F=$IH_SKEEMA_DEFAULTS_FILE,D=shop,t=small,h=db,P=3306\n",
    ERRORS,
    1,
    "/work",
)
# The same change with the wrappers blanked, which is how the preflight learns the table.
PLAIN_MULTILINE = SkeemaDiff(
    "-- instance: db:3306\n"
    "USE `shop`;\n"
    "ALTER TABLE `small` PARTITION BY RANGE  COLUMNS(created_at)\n"
    "(PARTITION pmax VALUES LESS THAN (MAXVALUE) ENGINE = InnoDB);\n",
    ERRORS,
    1,
    "/work",
)


def test_preflight_with_multiline_wrapper(server, tmp_path):  # pylint: disable=unused-argument
    """A wrapper command that spans lines is one statement, not a statement and a fragment."""
    digest_file = tmp_path / "digest"

    with mock.patch.object(Skeema, "diff", side_effect=[WRAPPED_MULTILINE, PLAIN_MULTILINE]):
        result = CliRunner().invoke(
            ih_skeema,
            ["--password", "secret", "preflight", "production", "--digest-file", str(digest_file)],
        )

    assert result.exit_code == 1, result.output
    assert "| `db:3306` | `shop` | `small` | ALTER | 16.0 KiB | alter-wrapper |" in result.output
    assert digest_file.read_text() == WRAPPED_MULTILINE.digest + "\n"
