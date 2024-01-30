"""
.. topic:: ``ih-ec2``

    A group of commands to work with AWS EC2 service.

    See ``ih-ec2 --help`` for more details.
"""
import sys
from logging import getLogger

import click
from boto3 import Session
from botocore.exceptions import (
    NoCredentialsError,
    NoRegionError,
    SSOTokenLoadError,
    TokenRetrievalError,
)

from infrahouse_toolkit.aws import aws_sso_login
from infrahouse_toolkit.aws.config import AWSConfig
from infrahouse_toolkit.cli.ih_ec2.cmd_instance_types import cmd_instance_types
from infrahouse_toolkit.cli.ih_ec2.cmd_launch import cmd_launch
from infrahouse_toolkit.cli.ih_ec2.cmd_launch_templates import cmd_launch_templates
from infrahouse_toolkit.cli.ih_ec2.cmd_list import cmd_list
from infrahouse_toolkit.cli.ih_ec2.cmd_subnets import cmd_subnets
from infrahouse_toolkit.cli.ih_ec2.cmd_terminate import cmd_terminate
from infrahouse_toolkit.logging import setup_logging

AWS_DEFAULT_REGION = "us-west-1"
LOG = getLogger(__name__)


def get_aws_regions() -> list:
    """
    :return: List of AWS regions.
    :rtype: list
    """
    return [
        "af-south-1",
        "ap-east-1",
        "ap-northeast-1",
        "ap-northeast-2",
        "ap-northeast-3",
        "ap-south-1",
        "ap-southeast-1",
        "ap-southeast-2",
        "ap-southeast-3",
        "ca-central-1",
        "eu-central-1",
        "eu-north-1",
        "eu-south-1",
        "eu-west-1",
        "eu-west-2",
        "eu-west-3",
        "me-south-1",
        "sa-east-1",
        "us-east-1",
        "us-east-2",
        "us-west-1",
        "us-west-2",
    ]


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
    type=click.Choice(get_aws_regions()),
    show_default=True,
    default=None,
)
@click.version_option()
@click.pass_context
def ih_ec2(ctx, **kwargs):
    """AWS EC2 helpers."""
    setup_logging(debug=kwargs["debug"])
    aws_profile = kwargs["aws_profile"]
    aws_config = AWSConfig()
    aws_region = kwargs["aws_region"]
    aws_session = None
    try:
        response = get_aws_client("sts", aws_profile, aws_region).get_caller_identity()

        LOG.info("Connected to AWS as %s", response["Arn"])
    except NoCredentialsError as err:
        LOG.error(err)
        LOG.info("Try to run ih-ec2 with --aws-profile option.")
        LOG.info("Available profiles:\n\t%s", "\n\t".join(aws_config.profiles))
        sys.exit(1)

    except (SSOTokenLoadError, TokenRetrievalError) as err:
        if not aws_profile:
            LOG.info("Try to run ih-ec2 with --aws-profile option.")
            LOG.info("Available profiles:\n\t%s", "\n\t".join(aws_config.profiles))
            sys.exit(1)
        LOG.debug(err)
        aws_session = aws_sso_login(aws_config, aws_profile, region=aws_region)
        response = get_aws_client("sts", aws_profile, aws_region, session=aws_session).get_caller_identity()

        LOG.info("Connected to AWS as %s", response["Arn"])

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


for cmd in [cmd_launch, cmd_list, cmd_instance_types, cmd_terminate, cmd_subnets, cmd_launch_templates]:
    # noinspection PyTypeChecker
    ih_ec2.add_command(cmd)


def get_aws_client(service_name: str, profile: str, region: str, session=None):
    """
    Get a client instance for an AWS service.

    :param service_name: AWS service e.g. ``ec2``.
    :param profile: AWS profile for authentication.
    :param region: AWS region.
    :param session: if an AWS session is passed, use it to create a client.
    :type session: Session
    :return: A client instance.
    """
    session = session or Session(region_name=region, profile_name=profile)
    return session.client(service_name)
