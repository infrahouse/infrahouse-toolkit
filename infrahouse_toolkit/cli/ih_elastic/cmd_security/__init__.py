"""
.. topic:: ``ih-elastic security``

    A ``ih-elastic security`` subcommand.

    See ``ih-elastic security --help`` for more details.
"""
from logging import getLogger

import click

from infrahouse_toolkit.cli.ih_elastic.cmd_security.cmd_api_key import cmd_api_key

LOG = getLogger(__name__)


@click.group(name="security")
def cmd_security():
    """
    Security APIs.
    """


for cmd in [cmd_api_key]:
    # noinspection PyTypeChecker
    cmd_security.add_command(cmd)
