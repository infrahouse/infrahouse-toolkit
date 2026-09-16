"""Unit tests for :py:mod:`infrahouse_toolkit.cli.ih_skeema.cmd_run`."""

import sys
from unittest import mock

import pytest
from click.testing import CliRunner

from infrahouse_toolkit.cli.ih_skeema import ih_skeema
from infrahouse_toolkit.skeema import Skeema, SkeemaDiff

# The package ``__init__`` binds ``cmd_run`` to the click command, which shadows the submodule,
# so the module has to come from ``sys.modules``.
_CMD_RUN = sys.modules["infrahouse_toolkit.cli.ih_skeema.cmd_run"]

PENDING = SkeemaDiff("-- instance: db:3306\nUSE `shop`;\nDROP TABLE `gone`;\n", "", 1, "/work")
REFUSED = SkeemaDiff("", "2026-09-16 11:52:35 [ERROR] # DROP TABLE `gone`\n", 2, "/work")


@pytest.fixture(name="popen")
def _popen():
    """Patch Popen so that skeema isn't actually executed, and pretend skeema is installed."""
    with mock.patch("infrahouse_toolkit.cli.ih_skeema.check_output", return_value=b"skeema version 1.11.1"):
        with mock.patch.object(_CMD_RUN, "Popen") as popen:
            popen.return_value.__enter__.return_value.returncode = 0
            yield popen


def _run(args, diff=PENDING):
    """
    Invoke ``ih-skeema run`` with ``Skeema.diff`` returning a fixed diff.

    :param args: Arguments after ``run``.
    :param diff: What ``Skeema.diff`` returns.
    :return: The click result and the ``Skeema.diff`` mock.
    """
    with mock.patch.object(Skeema, "diff", return_value=diff) as skeema_diff:
        result = CliRunner().invoke(ih_skeema, ["--password", "secret", "run"] + args)
    return result, skeema_diff


def test_push_with_expected_digest(popen):
    """The approved changes are pushed, and the digest is computed with the push's own arguments."""
    result, skeema_diff = _run(["push", "production", "--allow-unsafe", "--expect-digest", PENDING.digest])

    assert result.exit_code == 0, result.output
    skeema_diff.assert_called_once_with(["production", "--allow-unsafe"])
    assert popen.call_args.args[0] == ["skeema", "--user", "root", "push", "production", "--allow-unsafe"]


def test_push_with_changed_digest(popen):
    """Changes that moved since approval are not pushed."""
    result, _ = _run(["push", "production", "--expect-digest", "deadbeef"])

    assert result.exit_code == 2
    assert "expected digest deadbeef" in result.output
    popen.assert_not_called()


def test_push_when_diff_fails(popen):
    """If the diff can't be digested, nothing is pushed."""
    result, _ = _run(["push", "production", "--expect-digest", PENDING.digest], diff=REFUSED)

    assert result.exit_code == 2
    popen.assert_not_called()


def test_expect_digest_is_for_push_only(popen):
    """A digest check on anything but push is a usage error."""
    result, skeema_diff = _run(["diff", "production", "--expect-digest", PENDING.digest])

    assert result.exit_code == 2
    assert "--expect-digest only applies to push" in result.output
    skeema_diff.assert_not_called()
    popen.assert_not_called()


def test_push_without_digest(popen):
    """Without --expect-digest, push runs as before, with no extra diff."""
    result, skeema_diff = _run(["push", "production"])

    assert result.exit_code == 0, result.output
    skeema_diff.assert_not_called()
    popen.assert_called_once()


def test_run_without_password(popen):
    """Without a password from any source, skeema isn't run and the error says where to give one."""
    result = CliRunner(env={"MYSQL_PWD": None}).invoke(ih_skeema, ["run", "diff", "production"])

    assert result.exit_code == 2
    assert "No password for database user root" in result.output
    popen.assert_not_called()
