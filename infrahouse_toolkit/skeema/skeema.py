"""
Module for Skeema class - the skeema executable, run with credentials kept off its command line.
"""

from contextlib import contextmanager
from logging import getLogger
from os import defpath, environ, getcwd
from subprocess import PIPE, Popen
from typing import Dict, Iterator, List, Optional

from infrahouse_toolkit import DEFAULT_ENCODING
from infrahouse_toolkit.skeema.defaults_file import (
    DEFAULTS_FILE_VARIABLE,
    mysql_defaults_file,
)
from infrahouse_toolkit.skeema.diff import SkeemaDiff
from infrahouse_toolkit.skeema.exceptions import SkeemaError

LOG = getLogger(__name__)


class Skeema:
    """
    The skeema executable.

    :param path: Path to the skeema executable.
    :type path: str
    :param username: Database username.
    :type username: str
    :param password: Password for that user, ``None`` if none was given.
    :type password: str
    """

    def __init__(self, path: str, username: str, password: Optional[str]):
        self._path = path
        self._username = username
        self._password = password

    # --- Public properties ---

    @property
    def password(self) -> str:
        """
        A missing password is reported only when one is needed, so that ``--help`` works without credentials.

        :return: Database password.
        :rtype: str
        :raises SkeemaError: If no password was given.
        """
        if self._password is None:
            raise SkeemaError(
                f"No password for database user {self._username}. "
                "Pass --password, set $MYSQL_PWD or use --credentials-secret."
            )
        return self._password

    @property
    def username(self) -> str:
        """
        :return: Database username.
        :rtype: str
        """
        return self._username

    # --- Public methods ---

    def command(self, subcommand: str, args: List[str]) -> List[str]:
        """
        :param subcommand: skeema command, e.g. ``diff``.
        :type subcommand: str
        :param args: Arguments for the command.
        :type args: list
        :return: Command line to run.
        :rtype: list
        """
        return [self._path, "--user", self._username, subcommand] + args

    def diff(self, args: List[str]) -> SkeemaDiff:
        """
        Run ``skeema diff`` in the current directory and capture what it prints.

        :param args: Arguments for skeema diff: the environment and options.
        :type args: list
        :return: The diff.
        :rtype: SkeemaDiff
        """
        cmd = self.command("diff", args)
        with self.environment() as env:
            with Popen(cmd, env=env, stdout=PIPE, stderr=PIPE) as proc:
                LOG.debug("Launched command: %s", " ".join(cmd))
                output, errors = proc.communicate()

        return SkeemaDiff(
            output.decode(DEFAULT_ENCODING),
            errors.decode(DEFAULT_ENCODING),
            proc.returncode,
            getcwd(),
        )

    @contextmanager
    def environment(self) -> Iterator[Dict[str, str]]:
        """
        Environment to run skeema in. The defaults file it names is removed when the block exits.

        :return: Context manager yielding the environment variables.
        :raises SkeemaError: If no password was given.
        """
        password = self.password
        with mysql_defaults_file(self._username, password) as defaults_path:
            yield {
                "MYSQL_PWD": password,
                DEFAULTS_FILE_VARIABLE: defaults_path,
                # pt-online-schema-change is #!/usr/bin/env perl and needs a PATH.
                "PATH": environ.get("PATH", defpath),
            }
