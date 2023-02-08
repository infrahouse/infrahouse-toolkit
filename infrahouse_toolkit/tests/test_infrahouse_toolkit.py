#!/usr/bin/env python

"""Tests for `infrahouse_toolkit` package."""

from click.testing import CliRunner

from infrahouse_toolkit import cli


def test_content(response):
    """Sample pytest test function with the pytest fixture as an argument."""
    print(response)
    # from bs4 import BeautifulSoup
    # assert 'GitHub' in BeautifulSoup(response.content).title.string


def test_command_line_interface():
    """Test the CLI."""
    runner = CliRunner()
    result = runner.invoke(cli.main)
    assert result.exit_code == 0
    assert "infrahouse_toolkit.cli.main" in result.output
    help_result = runner.invoke(cli.main, ["--help"])
    assert help_result.exit_code == 0
    assert "--help  Show this message and exit." in help_result.output
