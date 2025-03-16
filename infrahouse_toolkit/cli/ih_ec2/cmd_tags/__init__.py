"""
.. topic:: ``ih-ec2 tags``

    A ``ih-ec2 tags`` subcommand.

    See ``ih-ec2 tags`` for more details.
"""

import json
from logging import getLogger

import click
from infrahouse_core.aws.ec2_instance import EC2Instance

from infrahouse_toolkit.logging import setup_logging

LOG = getLogger()


@click.command(
    name="tags",
)
@click.argument("instance_id", required=False)
@click.pass_context
def cmd_tags(ctx, **kwargs):
    """
    List EC2 instance tags.

    By default, it will show tags of the local instance.

    """
    setup_logging(debug=ctx.obj["debug"])
    instance = EC2Instance(instance_id=kwargs["instance_id"], ec2_client=ctx.obj["ec2_client"])
    print(json.dumps(instance.tags, indent=4))
