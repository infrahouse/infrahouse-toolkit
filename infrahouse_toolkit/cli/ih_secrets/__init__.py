"""
.. topic:: ``ih-secrets``

    A group of commands to work with AWS Secrets Manager.

    See ``ih-secrets --help`` for more details.
"""

import sys
from logging import getLogger

import click
from botocore.exceptions import NoRegionError

from infrahouse_toolkit.aws import get_aws_client, get_aws_session
from infrahouse_toolkit.aws.config import AWSConfig
from infrahouse_toolkit.cli.ih_secrets.cmd_get import cmd_get
from infrahouse_toolkit.cli.ih_secrets.cmd_list import cmd_list
from infrahouse_toolkit.cli.ih_secrets.cmd_set import cmd_set
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
    "--verbose",
    help="Print INFO and WARNING level messages.",
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
def ih_secrets(ctx, **kwargs):
    """AWS EC2 helpers."""
    setup_logging(debug=kwargs["debug"], quiet=not kwargs["verbose"])
    aws_profile = kwargs["aws_profile"]
    aws_region = kwargs["aws_region"]
    aws_config = AWSConfig()
    aws_session = get_aws_session(aws_config, aws_profile, aws_region)

    try:
        ctx.obj = {
            "debug": kwargs["debug"],
            "secretsmanager_client": get_aws_client("secretsmanager", aws_profile, aws_region, session=aws_session),
            "aws_config": aws_config,
        }
    except NoRegionError as err:
        LOG.error(err)
        LOG.error("Use the --aws-region option to specify the AWS region.")
        sys.exit(1)


for cmd in [cmd_list, cmd_get, cmd_set]:
    # noinspection PyTypeChecker
    ih_secrets.add_command(cmd)
