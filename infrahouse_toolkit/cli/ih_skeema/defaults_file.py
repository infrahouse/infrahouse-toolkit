"""
.. topic:: ``infrahouse_toolkit.cli.ih_skeema.defaults_file``

    A MySQL client defaults file for tools Skeema shells out to.

    Skeema itself takes the password from ``$MYSQL_PWD``, but an
    ``alter-wrapper`` such as ``pt-online-schema-change`` cannot: its DSN splits
    on unescaped commas, which RDS passwords are allowed to contain. Handing
    those tools a defaults file avoids the quoting problem and keeps the
    password out of the process list.
"""

import os
from contextlib import contextmanager
from tempfile import NamedTemporaryFile
from typing import Iterator

from infrahouse_toolkit import DEFAULT_ENCODING

DEFAULTS_FILE_VARIABLE = "IH_SKEEMA_DEFAULTS_FILE"


def quote_option_value(value: str) -> str:
    """
    Render a value safely for a MySQL option file.

    Option files treat ``#`` as a comment and expand ``\\s``, ``\\b``, ``\\t``,
    ``\\n`` and ``\\r`` inside values, so quoting alone is not enough. Verified
    against MySQL 8.0: only doubling backslashes *and* quoting survives every
    character RDS permits in a master password.

    :param value: Raw option value.
    :return: The value, escaped and wrapped in double quotes.
    """
    return '"{}"'.format(value.replace("\\", "\\\\"))


@contextmanager
def mysql_defaults_file(username: str, password: str) -> Iterator[str]:
    """
    Write a ``[client]`` defaults file and remove it when the block exits.

    :param username: Database username.
    :param password: Password for that user.
    :return: Context manager yielding the path to the defaults file.
    """
    handle = NamedTemporaryFile(
        mode="w",
        prefix="ih-skeema-",
        suffix=".cnf",
        delete=False,
        encoding=DEFAULT_ENCODING,
    )
    try:
        # NamedTemporaryFile is already 0600; restated because this holds a credential.
        os.chmod(handle.name, 0o600)
        handle.write(f"[client]\nuser={quote_option_value(username)}\npassword={quote_option_value(password)}\n")
        handle.close()
        yield handle.name
    finally:
        handle.close()
        os.unlink(handle.name)
