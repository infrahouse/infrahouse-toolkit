"""
.. topic:: ``ih-aws autoscaling cancel-instance-refresh``

    A ``ih-aws autoscaling cancel-instance-refresh`` subcommand.

    See ``ih-aws autoscaling cancel-instance-refresh --help`` for more details.
"""

import sys
from logging import getLogger

import click
from botocore.exceptions import BotoCoreError, ClientError
from infrahouse_core.aws.asg import ASG
from infrahouse_core.aws.asg_instance import ASGInstance
from requests import RequestException

LOG = getLogger()


@click.command(name="cancel-instance-refresh")
@click.argument("asg_name", required=False)
@click.pass_context
def cmd_cancel_instance_refresh(ctx, **kwargs):
    """
    Cancel the active instance refresh of an autoscaling group.

    ASG_NAME is the autoscaling group name. If omitted, the group of the local EC2 instance is used.
    A group without an active instance refresh is not an error.
    """
    session = ctx.obj["aws_session"]
    asg_name = kwargs["asg_name"]
    try:
        if asg_name is None:
            instance = ASGInstance(session=session)
            try:
                asg_name = instance.asg_name
            except KeyError:
                LOG.error("Instance %s is not a member of an autoscaling group.", instance.instance_id)
                sys.exit(1)

        ASG(asg_name, session=session).cancel_instance_refresh()
        LOG.info("Requested to cancel the instance refresh of %s.", asg_name)

    except (BotoCoreError, ClientError, RequestException) as err:
        LOG.error(err)
        sys.exit(1)
