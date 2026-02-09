"""
.. topic:: ``ih-aws resources``

    A ``ih-aws resources`` subcommand group for tag-based resource
    discovery and cleanup.

    See ``ih-aws resources --help`` for more details.
"""

from logging import getLogger

import click

from infrahouse_toolkit.cli.ih_aws.cmd_resources.cmd_delete import cmd_delete
from infrahouse_toolkit.cli.ih_aws.cmd_resources.cmd_list import cmd_list

LOG = getLogger(__name__)


@click.group(name="resources")
def cmd_resources() -> None:
    """
    Discover and manage AWS resources by tags.
    """


for cmd in [
    cmd_list,
    cmd_delete,
]:
    # noinspection PyTypeChecker
    cmd_resources.add_command(cmd)
