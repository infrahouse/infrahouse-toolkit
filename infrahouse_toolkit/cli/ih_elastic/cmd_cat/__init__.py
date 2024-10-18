"""
.. topic:: ``ih-elastic cat``

    A ``ih-elastic cat`` subcommand.

    See ``ih-elastic cat --help`` for more details.
"""

from logging import getLogger

import click

from infrahouse_toolkit.cli.ih_elastic.cmd_cat.cmd_nodes import cmd_nodes
from infrahouse_toolkit.cli.ih_elastic.cmd_cat.cmd_repositories import cmd_repositories
from infrahouse_toolkit.cli.ih_elastic.cmd_cat.cmd_shards import cmd_shards
from infrahouse_toolkit.cli.ih_elastic.cmd_cat.cmd_snapshots import cmd_snapshots

LOG = getLogger(__name__)


@click.group(name="cat")
def cmd_cat():
    """
    Compact and aligned text (CAT) APIs.
    """


for cmd in [cmd_repositories, cmd_snapshots, cmd_shards, cmd_nodes]:
    # noinspection PyTypeChecker
    cmd_cat.add_command(cmd)
