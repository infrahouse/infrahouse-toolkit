"""
.. topic:: ``ih-aws autoscaling``

    A ``ih-aws autoscaling`` subcommand.

    See ``ih-aws autoscaling --help`` for more details.
"""

from logging import getLogger

import click

from infrahouse_toolkit.cli.ih_aws.cmd_autoscaling.cmd_mark_unhealthy import (
    cmd_mark_unhealthy,
)

LOG = getLogger()


@click.group(name="autoscaling")
def cmd_autoscaling():
    """
    AWS autoscaling Commands.
    """


for cmd in [
    cmd_mark_unhealthy,
]:
    # noinspection PyTypeChecker
    cmd_autoscaling.add_command(cmd)
