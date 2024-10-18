"""
.. topic:: ``ih-elastic security api-key``

    A ``ih-elastic security api-key`` subcommand.

    See ``ih-elastic security api-key --help`` for more details.
"""

from logging import getLogger

import click

from infrahouse_toolkit.cli.ih_elastic.cmd_security.cmd_api_key.cmd_create import (
    cmd_create,
)
from infrahouse_toolkit.cli.ih_elastic.cmd_security.cmd_api_key.cmd_delete import (
    cmd_delete,
)
from infrahouse_toolkit.cli.ih_elastic.cmd_security.cmd_api_key.cmd_list import cmd_list

LOG = getLogger(__name__)


@click.group(name="api-key")
def cmd_api_key():
    """
    Work with API keys.
    """


for cmd in [cmd_list, cmd_create, cmd_delete]:
    # noinspection PyTypeChecker
    cmd_api_key.add_command(cmd)
