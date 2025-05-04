"""
.. topic:: ``ih-aws autoscaling complete``

    A ``ih-aws autoscaling complete`` subcommand.

    See ``ih-aws autoscaling complete --help`` for more details.
"""

import sys
from logging import getLogger

import click
from botocore.exceptions import ClientError
from infrahouse_core.aws.asg import ASG
from infrahouse_core.aws.asg_instance import ASGInstance

LOG = getLogger()


@click.command(name="complete")
@click.option(
    "--result",
    help="Lifecycle action result",
    type=click.Choice(["ABANDON", "CONTINUE"]),
    default="CONTINUE",
    show_default=True,
)
@click.argument("hook_name")
@click.argument("instance_id", required=False)
def cmd_complete(**kwargs):
    """
    Complete a lifecycle action for a given hook name and a local or remote EC2 instance.
    """
    try:
        instance = ASGInstance(kwargs["instance_id"])
        ASG(instance.asg_name).complete_lifecycle_action(
            kwargs["hook_name"], result=kwargs["result"], instance_id=instance.instance_id
        )
        LOG.info("Lifecycle hook %s is complete with result %s", kwargs["hook_name"], kwargs["result"])

    except ClientError as err:
        LOG.error(err)
        sys.exit(1)
