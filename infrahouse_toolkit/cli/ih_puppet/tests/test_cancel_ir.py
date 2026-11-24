"""Unit tests for ``_cancel_ir()`` in :py:mod:`infrahouse_toolkit.cli.ih_puppet.cmd_apply`."""

import logging
import os
import sys
import time
from contextlib import nullcontext
from unittest import mock

import pytest

from infrahouse_toolkit.cli.ih_puppet.cmd_apply import _cancel_ir
from infrahouse_toolkit.cli.ih_puppet.tests.fake_executable import FakeExecutable

# The package ``__init__`` binds ``cmd_apply`` to the click command, which shadows the submodule,
# so the module has to come from ``sys.modules``.
_CMD_APPLY = sys.modules["infrahouse_toolkit.cli.ih_puppet.cmd_apply"]

# The timeout for tests whose child hangs: long enough for a slow fork to start the child and let it
# record its call, short enough to keep the test quick. Children that don't hang keep the real timeout.
HANG_TIMEOUT = 5


@pytest.mark.parametrize(
    "debug, quiet, args",
    [
        (False, True, "autoscaling cancel-instance-refresh"),
        (False, False, "--verbose autoscaling cancel-instance-refresh"),
        (True, True, "--debug autoscaling cancel-instance-refresh"),
        (True, False, "--debug --verbose autoscaling cancel-instance-refresh"),
    ],
)
def test_runs_ih_aws_next_to_python(fake_ih_aws, debug, quiet, args):
    """The child is the ``ih-aws`` next to ``sys.executable``, with logging flags that follow ``ih-puppet``'s."""
    _cancel_ir(debug=debug, quiet=quiet)

    assert fake_ih_aws.calls == [f"{fake_ih_aws.path} {args}"]


def test_falls_back_to_path(fake_ih_aws, tmp_path, monkeypatch):
    """Without ``ih-aws`` next to the interpreter, the one on ``PATH`` runs."""
    fake_ih_aws.path.unlink()
    path_dir = tmp_path / "path"
    path_dir.mkdir()
    on_path = FakeExecutable(path_dir / "ih-aws")
    on_path.write()
    monkeypatch.setenv("PATH", f"{path_dir}:/usr/bin:/bin")

    _cancel_ir(quiet=True)

    assert on_path.calls == [f"{on_path.path} autoscaling cancel-instance-refresh"]


def test_ih_aws_not_found(fake_ih_aws, caplog):
    """No ``ih-aws`` anywhere is a failed cancel: logged, not raised."""
    fake_ih_aws.path.unlink()

    with caplog.at_level(logging.WARNING):
        _cancel_ir()

    assert _warnings(caplog) == [
        f"Couldn't cancel the instance refresh: ih-aws is neither next to {sys.executable} nor on PATH"
    ]


def test_child_fails(fake_ih_aws, caplog):
    """A child that exits non-zero is a failed cancel: logged, not raised."""
    fake_ih_aws.write("exit 3")

    with caplog.at_level(logging.WARNING):
        _cancel_ir()

    assert len(fake_ih_aws.calls) == 1
    [warning] = _warnings(caplog)
    assert "returned non-zero exit status 3" in warning


def test_child_times_out(fake_ih_aws, tmp_path, caplog):
    """A child that hangs is killed and reaped after the timeout: logged, not raised."""
    pid_file = tmp_path / "ih-aws.pid"
    fake_ih_aws.write(f"echo $$ > {pid_file}\nexec sleep 60")

    started = time.monotonic()
    with mock.patch.object(_CMD_APPLY, "CANCEL_IR_TIMEOUT", HANG_TIMEOUT), caplog.at_level(logging.WARNING):
        _cancel_ir()

    assert time.monotonic() - started < 30
    [warning] = _warnings(caplog)
    assert "timed out after" in warning
    with pytest.raises(ProcessLookupError):
        os.kill(int(pid_file.read_text()), 0)


def test_child_cannot_start(fake_ih_aws, caplog):
    """
    An ``ih-aws`` whose interpreter is gone, as in the middle of a package upgrade,
    fails to launch with ``OSError``: logged, not raised.
    """
    fake_ih_aws.write(interpreter="/nonexistent/embedded/bin/python3.11")

    with caplog.at_level(logging.WARNING):
        _cancel_ir()

    [warning] = _warnings(caplog)
    assert "No such file or directory" in warning


@pytest.mark.parametrize(
    "body, timeout, warnings",
    [
        ("exit 0", None, []),
        ("exit 1", None, ["returned non-zero exit status 1"]),
        ("exec sleep 60", HANG_TIMEOUT, ["timed out after"]),
    ],
    ids=["succeeds", "fails", "hangs"],
)
def test_no_imports_on_cancel_path(fake_ih_aws, caplog, body, timeout, warnings):
    """
    The cancel path imports nothing at run time.

    After Puppet upgrades the package under a running ``ih-puppet``, any import that isn't
    already done fails, so here every import raises ``ImportError``.
    """
    fake_ih_aws.write(body)
    short_timeout = mock.patch.object(_CMD_APPLY, "CANCEL_IR_TIMEOUT", timeout) if timeout else nullcontext()

    with short_timeout, caplog.at_level(logging.WARNING), mock.patch(
        "builtins.__import__", side_effect=ImportError("the install tree is gone")
    ):
        _cancel_ir()

    assert len(fake_ih_aws.calls) == 1
    logged = _warnings(caplog)
    assert len(logged) == len(warnings), logged
    for expected, warning in zip(warnings, logged):
        assert expected in warning


def _warnings(caplog) -> list:
    return [record.getMessage() for record in caplog.records if record.levelno == logging.WARNING]
