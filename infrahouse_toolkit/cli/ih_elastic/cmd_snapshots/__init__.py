"""
.. topic:: ``ih-elastic snapshots``

    A ``ih-elastic snapshots`` subcommand.

    See ``ih-elastic snapshots --help`` for more details.
"""

from logging import getLogger

import click

from infrahouse_toolkit.cli.ih_elastic.cmd_snapshots.cmd_create import cmd_create
from infrahouse_toolkit.cli.ih_elastic.cmd_snapshots.cmd_create_repository import (
    cmd_create_repository,
)
from infrahouse_toolkit.cli.ih_elastic.cmd_snapshots.cmd_delete_repository import (
    cmd_delete_repository,
)
from infrahouse_toolkit.cli.ih_elastic.cmd_snapshots.cmd_restore import cmd_restore
from infrahouse_toolkit.cli.ih_elastic.cmd_snapshots.cmd_status import cmd_status

LOG = getLogger(__name__)


@click.group(name="snapshots")
def cmd_snapshots():
    """
    Work with snapshots.
    """


for cmd in [cmd_status, cmd_create_repository, cmd_delete_repository, cmd_create, cmd_restore]:
    # noinspection PyTypeChecker
    cmd_snapshots.add_command(cmd)
