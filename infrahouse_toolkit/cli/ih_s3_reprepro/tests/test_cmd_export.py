"""Unit tests for :py:mod:`infrahouse_toolkit.cli.ih_s3_reprepro.cmd_export`."""

import sys
from contextlib import contextmanager
from unittest import mock

from click.testing import CliRunner

from infrahouse_toolkit.cli.ih_s3_reprepro import ih_s3_reprepro

# The package ``__init__`` binds the name ``cmd_export`` to the click Command object
# (``from ...cmd_export import cmd_export``), which shadows the same-named submodule in
# the package namespace. So neither the dotted patch target
# "...cmd_export.repo_env" nor ``import ...cmd_export as m`` reaches the module -- both
# resolve to the Command object. Grab the real module from ``sys.modules`` and patch it
# with ``patch.object`` instead.
_CMD_EXPORT = sys.modules["infrahouse_toolkit.cli.ih_s3_reprepro.cmd_export"]


@contextmanager
def _fake_repo_env(*args, **kwargs):
    """Stand in for ``repo_env``: yield a fixed (mount_path, gpg_home) tuple."""
    yield "/mnt/repo", "/tmp/gpghome"


def _run(args):
    """
    Invoke ``ih-s3-reprepro ... export`` with ``repo_env`` and ``execute`` mocked out.

    :param args: Arguments passed after the top-level group options.
    :type args: list
    :return: The mock standing in for ``execute`` so the caller can assert on the command line.
    :rtype: mock.MagicMock
    """
    base = [
        "--bucket",
        "test-bucket",
        "--role-arn",
        "arn:aws:iam::123456789012:role/packager",
        "--gpg-key-secret-id",
        "packager-key-noble",
        "--gpg-passphrase-secret-id",
        "packager-passphrase-noble",
    ]
    with mock.patch("infrahouse_toolkit.cli.ih_s3_reprepro.check_dependencies"), mock.patch.object(
        _CMD_EXPORT, "repo_env", _fake_repo_env
    ), mock.patch.object(_CMD_EXPORT, "execute") as mock_execute:
        result = CliRunner().invoke(ih_s3_reprepro, base + args, catch_exceptions=False)
    assert result.exit_code == 0, result.output
    return mock_execute


def test_export_single_codename():
    """Happy path: ``export noble`` runs ``reprepro ... export noble`` in the mounted repo."""
    mock_execute = _run(["export", "noble"])
    mock_execute.assert_called_once_with(
        ["reprepro", "-V", "-b", "/mnt/repo", "--gnupghome", "/tmp/gpghome", "export", "noble"]
    )


def test_export_multiple_codenames():
    """Multiple distributions are all appended to the reprepro command."""
    mock_execute = _run(["export", "noble", "jammy"])
    mock_execute.assert_called_once_with(
        ["reprepro", "-V", "-b", "/mnt/repo", "--gnupghome", "/tmp/gpghome", "export", "noble", "jammy"]
    )


def test_export_no_codename_exports_all():
    """With no codename, ``reprepro export`` is invoked bare so every distribution is exported."""
    mock_execute = _run(["export"])
    mock_execute.assert_called_once_with(["reprepro", "-V", "-b", "/mnt/repo", "--gnupghome", "/tmp/gpghome", "export"])
