"""Fixtures for ``ih-puppet`` tests."""

import sys

import pytest

from infrahouse_toolkit.cli.ih_puppet.tests.fake_executable import FakeExecutable


@pytest.fixture(name="fake_ih_aws")
def _fake_ih_aws(tmp_path, monkeypatch) -> FakeExecutable:
    """
    A fake ``ih-aws`` next to a fake ``sys.executable``, the way the package installs it.

    ``PATH`` is reduced to system directories, so a real ``ih-aws`` is never found.
    """
    bin_dir = tmp_path / "embedded" / "bin"
    bin_dir.mkdir(parents=True)
    monkeypatch.setattr(sys, "executable", str(bin_dir / "python3"))
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    fake = FakeExecutable(bin_dir / "ih-aws")
    fake.write()
    return fake
