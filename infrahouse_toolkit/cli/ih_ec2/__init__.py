"""
.. topic:: ``ih-ec2``

    A group of commands to work with AWS EC2 service.

    See ``ih-ec2 --help`` for more details.
"""

import sys
from logging import getLogger

import click
from botocore.exceptions import NoRegionError

from infrahouse_toolkit.aws import get_aws_client, get_aws_session
from infrahouse_toolkit.aws.config import AWSConfig
from infrahouse_toolkit.cli.ih_ec2.cmd_instance_types import cmd_instance_types
from infrahouse_toolkit.cli.ih_ec2.cmd_launch import cmd_launch
from infrahouse_toolkit.cli.ih_ec2.cmd_launch_templates import cmd_launch_templates
from infrahouse_toolkit.cli.ih_ec2.cmd_list import cmd_list
from infrahouse_toolkit.cli.ih_ec2.cmd_subnets import cmd_subnets
from infrahouse_toolkit.cli.ih_ec2.cmd_tags import cmd_tags
from infrahouse_toolkit.cli.ih_ec2.cmd_terminate import cmd_terminate
from infrahouse_toolkit.logging import setup_logging

AWS_DEFAULT_REGION = "us-west-1"
LOG = getLogger(__name__)


@click.group()
@click.option(
    "--debug",
    help="Enable debug logging.",
    is_flag=True,
    default=False,
    show_default=True,
)
@click.option(
    "--aws-profile",
    help="AWS profile name for authentication.",
    type=click.Choice(AWSConfig().profiles),
    default=None,
    show_default=True,
)
@click.option(
    "--aws-region",
    help="AWS region to use.",
    type=click.Choice(AWSConfig().regions),
    show_default=True,
    default=None,
)
@click.version_option()
@click.pass_context
def ih_ec2(ctx, **kwargs):
    """AWS EC2 helpers."""
    if kwargs["debug"]:
        setup_logging(debug=kwargs["debug"])

    aws_profile = kwargs["aws_profile"]
    aws_config = AWSConfig()
    aws_region = kwargs["aws_region"]
    aws_session = get_aws_session(aws_config, aws_profile, aws_region)

    try:
        ctx.obj = {
            "debug": kwargs["debug"],
            "ec2_client": get_aws_client("ec2", aws_profile, aws_region, session=aws_session),
            "aws_config": aws_config,
        }
    except NoRegionError as err:
        LOG.error(err)
        LOG.error("Use the --aws-region option to specify the AWS region.")
        sys.exit(1)


for cmd in [cmd_launch, cmd_list, cmd_instance_types, cmd_terminate, cmd_subnets, cmd_launch_templates, cmd_tags]:
    # noinspection PyTypeChecker
    ih_ec2.add_command(cmd)
