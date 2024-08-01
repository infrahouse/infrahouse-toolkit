"""
.. topic:: ``ih-aws ecs``

    A ``ih-aws ecs`` subcommand.

    See ``ih-aws ecs --help`` for more details.
"""

from logging import getLogger

import click

from infrahouse_toolkit.cli.ih_aws.cmd_ecs.cmd_wait_services_stable import (
    cmd_wait_services_stable,
)

LOG = getLogger(__name__)


@click.group(name="ecs")
def cmd_ecs():
    """
    AWS ECS Commands.
    """


for cmd in [
    cmd_wait_services_stable,
]:
    # noinspection PyTypeChecker
    cmd_ecs.add_command(cmd)
