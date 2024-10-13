"""
.. topic:: ``ih-aws autoscaling mark-unhealthy``

    A ``ih-aws autoscaling mark-unhealthy`` subcommand.

    See ``ih-aws autoscaling mark-unhealthy --help`` for more details.
"""

import sys
from logging import getLogger

import click
from botocore.exceptions import ClientError

from infrahouse_toolkit.aws.asg_instance import ASGInstance

LOG = getLogger()


@click.command(name="mark-unhealthy")
@click.argument("instance_id", required=False)
def cmd_mark_unhealthy(**kwargs):
    """
    Mark instance Unhealthy so Autoscaling group will replace it.
    """
    try:
        ASGInstance(kwargs["instance_id"]).mark_unhealthy()

    except ClientError as err:
        LOG.error(err)
        sys.exit(1)
