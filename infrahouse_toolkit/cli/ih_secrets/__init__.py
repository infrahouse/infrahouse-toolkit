"""
.. topic:: ``ih-secrets``

    A group of commands to work with AWS Secrets Manager.

    See ``ih-secrets --help`` for more details.
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
from infrahouse_toolkit.cli.ih_secrets.cmd_get import cmd_get
from infrahouse_toolkit.cli.ih_secrets.cmd_list import cmd_list
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
def ih_secrets(ctx, **kwargs):
    """AWS EC2 helpers."""
    setup_logging(debug=kwargs["debug"])
    aws_profile = kwargs["aws_profile"]
    aws_region = kwargs["aws_region"]
    aws_config = AWSConfig()
    aws_session = None
    try:
        response = get_aws_client("sts", aws_profile, aws_region).get_caller_identity()

        LOG.info("Connected to AWS as %s", response["Arn"])
    except NoCredentialsError as err:
        LOG.error(err)
        LOG.info("Try to run ih-secrets with --aws-profile option.")
        LOG.info("Available profiles:\n\t%s", "\n\t".join(aws_config.profiles))
        sys.exit(1)

    except (SSOTokenLoadError, TokenRetrievalError) as err:
        if not aws_profile:
            LOG.info("Try to run ih-secrets with --aws-profile option.")
            LOG.info("Available profiles:\n\t%s", "\n\t".join(aws_config.profiles))
            sys.exit(1)
        LOG.debug(err)
        aws_session = aws_sso_login(aws_config, aws_profile, region=aws_region)
        response = get_aws_client("sts", aws_profile, aws_region, session=aws_session).get_caller_identity()

        LOG.info("Connected to AWS as %s", response["Arn"])

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


for cmd in [cmd_list, cmd_get]:
    # noinspection PyTypeChecker
    ih_secrets.add_command(cmd)


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
