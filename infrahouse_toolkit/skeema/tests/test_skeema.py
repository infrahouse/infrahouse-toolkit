"""Unit tests for :py:mod:`infrahouse_toolkit.skeema.skeema`."""

import os

import pytest

from infrahouse_toolkit.skeema.defaults_file import DEFAULTS_FILE_VARIABLE
from infrahouse_toolkit.skeema.exceptions import SkeemaError
from infrahouse_toolkit.skeema.skeema import Skeema


def test_environment():
    """skeema gets the password in $MYSQL_PWD, and its wrappers get a defaults file."""
    with Skeema("skeema", "admin", "secret").environment() as env:
        assert env["MYSQL_PWD"] == "secret"
        assert os.path.exists(env[DEFAULTS_FILE_VARIABLE])


def test_environment_without_password():
    """No password is an error that says where to give one, not a traceback from the defaults file."""
    with pytest.raises(SkeemaError, match="No password for database user admin"):
        with Skeema("skeema", "admin", None).environment():
            pass
