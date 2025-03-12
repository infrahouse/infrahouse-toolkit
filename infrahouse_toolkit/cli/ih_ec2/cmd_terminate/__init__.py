"""
.. topic:: ``ih-ec2 terminate``

    A ``ih-ec2 terminate`` subcommand.

    See ``ih-ec2 terminate`` for more details.
"""

import sys
from logging import getLogger

import click

from infrahouse_toolkit.cli.ih_ec2.cmd_list import list_ec2_instances
from infrahouse_toolkit.logging import setup_logging

LOG = getLogger()


def terminate_ec2_instance(ec2_client, instance_id):
    """Terminate an EC2 instance."""
    ec2_client.terminate_instances(
        InstanceIds=[
            instance_id,
        ],
    )
    LOG.info("Successfully terminated %s", instance_id)


@click.command(name="terminate")
@click.argument("instance_id", required=False)
@click.pass_context
def cmd_terminate(ctx, instance_id):
    """
    Terminate an EC2 instance.
    """
    setup_logging(debug=ctx.obj["debug"])
    ec2_client = ctx.obj["ec2_client"]
    if not instance_id:
        LOG.error("Please specify INSTANCE_ID from following:")
        list_ec2_instances(ec2_client)
        sys.exit(1)

    if click.prompt(f"Are you sure you want to terminate {instance_id}? (yes/no)"):
        terminate_ec2_instance(ctx.obj["ec2_client"], instance_id)
