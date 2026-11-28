"""Unit tests for ``install_module_dependencies()`` in :py:mod:`infrahouse_toolkit.cli.ih_puppet.cmd_apply`."""

import logging

from infrahouse_toolkit.cli.ih_puppet.cmd_apply import install_module_dependencies


def test_file_isnt_a_module(tmp_path, caplog):
    """A plain file among the modules is skipped, and the log names it."""
    not_a_module = tmp_path / "README.md"
    not_a_module.write_text("not a puppet module\n")

    with caplog.at_level(logging.INFO):
        install_module_dependencies(str(tmp_path))

    assert f"{not_a_module} isn't a puppet module" in caplog.messages
