"""
.. topic:: ``ih-elastic cat``

    A ``ih-elastic cat`` subcommand.

    See ``ih-elastic cat --help`` for more details.
"""

import logging

import click

from infrahouse_toolkit.cli.ih_elastic.cmd_cat.cmd_repositories import cmd_repositories
from infrahouse_toolkit.cli.ih_elastic.cmd_cat.cmd_snapshots import cmd_snapshots

LOG = logging.getLogger()


@click.group(name="cat")
def cmd_cat():
    """
    Compact and aligned text (CAT) APIs.
    """


for cmd in [cmd_repositories, cmd_snapshots]:
    # noinspection PyTypeChecker
    cmd_cat.add_command(cmd)
