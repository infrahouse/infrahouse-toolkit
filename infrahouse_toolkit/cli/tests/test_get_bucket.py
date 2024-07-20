"""Unit tests for :py:func:`infrahouse_toolkit.cli.lib.get_bucket`."""

from infrahouse_toolkit.cli.lib import get_bucket


def test_get_bucket(terraform_tf):
    """Check that :py:func:`infrahouse_toolkit.cli.lib.get_bucket` can parse a valid ``terraform.tf``."""
    assert get_bucket(tf_file=terraform_tf) == "infrahouse-foo"
