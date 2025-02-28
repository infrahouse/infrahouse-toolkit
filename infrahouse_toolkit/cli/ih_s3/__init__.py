"""
.. topic:: ``ih-s3``

    A group of commands to work with AWS S3 service.

    See ``ih-s3 --help`` for more details.
"""

import sys
from logging import getLogger

import click
from botocore.exceptions import NoRegionError
from infrahouse_core.aws import AWSConfig, get_aws_client, get_aws_session

from infrahouse_toolkit.cli.ih_s3.cmd_upload_logs import cmd_upload_logs
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
def ih_s3(ctx, **kwargs):
    """AWS S3 helpers."""
    setup_logging(debug=kwargs["debug"])

    aws_profile = kwargs["aws_profile"]
    aws_config = AWSConfig()
    aws_region = kwargs["aws_region"]
    aws_session = get_aws_session(aws_config, aws_profile, aws_region)

    try:
        ctx.obj = {
            "debug": kwargs["debug"],
            "s3_client": get_aws_client("s3", aws_profile, aws_region, session=aws_session),
            "aws_config": aws_config,
        }
    except NoRegionError as err:
        LOG.error(err)
        LOG.error("Use the --aws-region option to specify the AWS region.")
        sys.exit(1)


for cmd in [cmd_upload_logs]:
    # noinspection PyTypeChecker
    ih_s3.add_command(cmd)
