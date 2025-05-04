"""
.. topic:: ``ih-aws autoscaling scale-in``

    A ``ih-aws autoscaling scale-in`` subcommand.

    See ``ih-aws autoscaling scale-in --help`` for more details.
"""

import sys
from logging import getLogger

import click
from botocore.exceptions import ClientError
from infrahouse_core.aws.asg_instance import ASGInstance

LOG = getLogger()


@click.command(name="scale-in")
@click.argument("action", type=click.Choice(["enable-protection", "disable-protection"]))
@click.argument("instance_id", required=False)
def cmd_scale_in(**kwargs):
    """
    scale-in EC2 instance from scale-in event.
    """
    try:
        instance = ASGInstance(kwargs["instance_id"])
        if kwargs["action"] == "enable-protection":
            instance.protect()
            LOG.info("Instance %s is protected from scale-in", instance.instance_id)
        else:
            instance.unprotect()
            LOG.info("Instance %s is unprotected from scale-in", instance.instance_id)

    except ClientError as err:
        LOG.error(err)
        sys.exit(1)
