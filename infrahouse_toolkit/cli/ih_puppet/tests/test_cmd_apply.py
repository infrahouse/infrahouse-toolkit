"""Unit tests for ``ih-puppet apply``: its exit code and the cancel of the instance refresh."""

import sys
from contextlib import nullcontext
from unittest import mock

import pytest
from click.testing import CliRunner, Result

from infrahouse_toolkit.cli.ih_puppet import ih_puppet
from infrahouse_toolkit.cli.ih_puppet.tests.fake_executable import FakeExecutable

# The package ``__init__`` binds ``cmd_apply`` to the click command, which shadows the submodule,
# so the module has to come from ``sys.modules``.
_CMD_APPLY = sys.modules["infrahouse_toolkit.cli.ih_puppet.cmd_apply"]

CANCEL_FLAG = "--cancel-instance-refresh-on-error"


@pytest.fixture(name="puppet")
def _puppet(fake_ih_aws, tmp_path, monkeypatch) -> FakeExecutable:
    """
    A fake ``puppet`` on ``PATH``, next to a fake ``ih-aws``.

    The system lock is patched out because it lives in ``/var/run``, and so is ``setup_logging()``,
    because it would replace pytest's log handlers.
    """
    path_dir = tmp_path / "puppet-bin"
    path_dir.mkdir()
    monkeypatch.setenv("PATH", f"{path_dir}:/usr/bin:/bin")
    fake = FakeExecutable(path_dir / "puppet")
    fake.write()
    with mock.patch.object(_CMD_APPLY, "SystemLock", return_value=nullcontext()):
        with mock.patch("infrahouse_toolkit.cli.ih_puppet.setup_logging"):
            yield fake


@pytest.mark.parametrize("puppet_code, exit_code", [(0, 0), (2, 0), (1, 1), (4, 4), (6, 6)])
def test_exit_code(puppet, fake_ih_aws, puppet_code, exit_code):
    """Puppet's detailed exit code maps to ``ih-puppet``'s, and without the flag nothing is cancelled."""
    puppet.write(f"exit {puppet_code}")

    result = _apply()

    assert result.exit_code == exit_code, result.output
    assert len(puppet.calls) == 2
    assert not fake_ih_aws.calls


@pytest.mark.parametrize("puppet_code, exit_code, cancels", [(0, 0, 0), (2, 0, 0), (1, 1, 1), (4, 4, 1), (6, 6, 1)])
def test_exit_code_with_cancel(puppet, fake_ih_aws, puppet_code, exit_code, cancels):
    """With the flag, a failed run cancels exactly once, and the exit code doesn't change."""
    puppet.write(f"exit {puppet_code}")

    result = _apply(CANCEL_FLAG)

    assert result.exit_code == exit_code, result.output
    assert fake_ih_aws.calls == [f"{fake_ih_aws.path} --verbose autoscaling cancel-instance-refresh"] * cancels


@pytest.mark.parametrize("puppet_code", [1, 4, 6])
def test_failed_cancel_keeps_exit_code(puppet, fake_ih_aws, puppet_code):
    """A failed cancel is attempted once and doesn't change the exit code."""
    puppet.write(f"exit {puppet_code}")
    fake_ih_aws.write("exit 1")

    result = _apply("--quiet", CANCEL_FLAG)

    assert result.exit_code == puppet_code, result.output
    assert fake_ih_aws.calls == [f"{fake_ih_aws.path} autoscaling cancel-instance-refresh"]


def test_cancel_when_apply_raises(puppet, fake_ih_aws):  # pylint: disable=unused-argument
    """
    An exception from the Puppet run exits 1 and cancels once.

    ``Popen`` raises as if ``puppet`` were missing. Unlinking the fake wouldn't do: ``_run_apply()``
    appends ``/opt/puppetlabs/bin`` to ``PATH``, where a host with puppet-agent has the real one.
    """
    with mock.patch.object(
        _CMD_APPLY, "Popen", side_effect=FileNotFoundError(2, "No such file or directory", "puppet")
    ):
        result = _apply(CANCEL_FLAG)

    assert result.exit_code == 1, result.output
    assert len(fake_ih_aws.calls) == 1


def test_cancel_is_not_retried(puppet):
    """
    An unexpected error from the cancel propagates, and the handler for errors in the Puppet run
    doesn't catch it to cancel a second time, as it did before IH-182.
    """
    puppet.write("exit 1")

    with mock.patch.object(_CMD_APPLY, "run", side_effect=RuntimeError("unexpected")) as run:
        result = _apply(CANCEL_FLAG)

    run.assert_called_once()
    assert isinstance(result.exception, RuntimeError)


def _apply(*options: str) -> Result:
    """
    Run ``ih-puppet [options] apply site.pp`` with a root directory that has no modules to install.
    """
    return CliRunner().invoke(ih_puppet, ["--root-directory", "/nonexistent", *options, "apply", "site.pp"])
