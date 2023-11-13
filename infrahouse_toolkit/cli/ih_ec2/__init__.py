"""
.. topic:: ``ih-ec2``

    A group of commands to work with AWS EC2 service.

    See ``ih-ec2 --help`` for more details.
"""
import sys
from configparser import ConfigParser
from os import path as osp

import click
from boto3 import Session
from botocore.exceptions import NoCredentialsError

from infrahouse_toolkit import LOG
from infrahouse_toolkit.cli.ih_ec2.cmd_instance_types import cmd_instance_types
from infrahouse_toolkit.cli.ih_ec2.cmd_launch import cmd_launch
from infrahouse_toolkit.cli.ih_ec2.cmd_list import cmd_list
from infrahouse_toolkit.cli.ih_ec2.cmd_terminate import cmd_terminate
from infrahouse_toolkit.logging import setup_logging

AWS_DEFAULT_REGION = "us-west-1"
AWS_DEFAULT_PROIFLE = "default"


def get_aws_profiles() -> list:
    """
    Parse AWS common configuration files and return a list of known AWS profiles.

    :return: List of configured AWS profiles.
    :rtype: list
    """
    profiles = {AWS_DEFAULT_PROIFLE}
    for cred_file in ["config", "credentials"]:
        config = ConfigParser()
        config.read(osp.expanduser(osp.join("~/.aws", cred_file)))
        for section in config.sections():
            if section.startswith("profile"):
                profiles.add(section.split(" ")[1])

    return list(profiles)


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
    type=click.Choice(get_aws_profiles()),
    default=AWS_DEFAULT_PROIFLE,
    show_default=True,
)
@click.option(
    "--aws-region",
    help="AWS region to use.",
    type=click.Choice(get_aws_regions()),
    show_default=True,
    default=AWS_DEFAULT_REGION,
)
@click.version_option()
@click.pass_context
def ih_ec2(ctx, **kwargs):
    """AWS EC2 helpers."""
    setup_logging(LOG, debug=kwargs["debug"])
    try:
        response = get_aws_client("sts", kwargs["aws_profile"], kwargs["aws_region"]).get_caller_identity()

        LOG.info("Connected to AWS as %s", response["Arn"])
    except NoCredentialsError as err:
        LOG.error(err)
        LOG.info("Try to run ih-ec2 with --aws-profile option.")
        LOG.info("Available profiles:\n\t%s", "\n\t".join(get_aws_profiles()))
        sys.exit(1)

    ctx.obj = {
        "debug": kwargs["debug"],
        "ec2_client": get_aws_client("ec2", kwargs["aws_profile"], kwargs["aws_region"]),
    }


for cmd in [cmd_launch, cmd_list, cmd_instance_types, cmd_terminate]:
    # noinspection PyTypeChecker
    ih_ec2.add_command(cmd)


def get_aws_client(service_name: str, profile: str, region: str):
    """
    Get a client instance for an AWS service.

    :param service_name: AWS service e.g. ``ec2``.
    :param profile: AWS profile for authentication.
    :param region: AWS region.
    :return: A client instance.
    """
    session = Session(region_name=region, profile_name=profile)
    return session.client(service_name)
