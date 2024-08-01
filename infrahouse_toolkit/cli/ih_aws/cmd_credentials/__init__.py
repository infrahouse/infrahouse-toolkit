"""
.. topic:: ``ih-aws credentials``

    A ``ih-aws credentials`` subcommand.

    See ``ih-aws credentials --help`` for more details.
"""

import sys
from logging import getLogger

import click
from botocore.exceptions import ClientError

from infrahouse_toolkit.aws import get_aws_client

LOG = getLogger(__name__)


@click.command(name="credentials")
@click.option("--docker", help="Generate command line arguments for docker", is_flag=True, default=False)
@click.option("--export", "-e", help="Add export keyword", is_flag=True, default=False)
@click.pass_context
def cmd_credentials(ctx, docker, export):
    """
    Print AWS temporary credentials
    """
    aws_config = ctx.obj["aws_config"]
    aws_profile = ctx.obj["aws_profile"]
    try:
        aws_session = ctx.obj["aws_session"]
        creds = {
            "AWS_ACCESS_KEY_ID": aws_session.get_credentials().access_key,
            "AWS_SECRET_ACCESS_KEY": aws_session.get_credentials().secret_key,
        }

        if aws_config.get_region(aws_profile):
            creds["AWS_DEFAULT_REGION"] = aws_config.get_region(aws_profile)

        if aws_session.get_credentials().token:
            creds["AWS_SESSION_TOKEN"] = aws_session.get_credentials().token

        response = get_aws_client(
            "sts", aws_profile, aws_config.get_region(aws_profile), session=aws_session
        ).get_caller_identity()
        LOG.debug("Connected to AWS as %s", response["Arn"])

        if docker:
            pairs = [f"-e {k}={v}" for k, v in creds.items()]
            sys.stdout.write(" ".join(pairs))
        else:
            pairs = [f"{'export ' if export else ''}{k}={v}" for k, v in creds.items()]
            print("\n".join(pairs))

    except ClientError as err:
        LOG.exception(err)
        LOG.error("Try to run ih-aws with --aws-profile option.")
        LOG.error("Available profiles:\n\t%s", "\n\t".join(aws_config.profiles))
        sys.exit(1)
