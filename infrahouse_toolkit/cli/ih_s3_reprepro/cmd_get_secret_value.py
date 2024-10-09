"""
.. topic:: ``ih-s3-reprepro get-secret-value``

    A ``ih-s3-reprepro get-secret-value`` subcommand.

    See ``ih-s3-reprepro get-secret-value --help`` for more details.
"""

import sys
from logging import getLogger

import click
from botocore.exceptions import BotoCoreError, ClientError
from click import Context

from infrahouse_toolkit.aws import get_client

LOG = getLogger()


@click.command(name="get-secret-value")
@click.argument("secret_id")
@click.pass_context
def cmd_get_secret_value(ctx: Context, secret_id):
    """
    Retrieve a secret value.
    """
    role_arn = ctx.parent.params["role_arn"]
    try:
        client = get_client("secretsmanager", role_arn=role_arn, region=ctx.parent.params["aws_region"])
        response = client.get_secret_value(
            SecretId=secret_id,
        )
        LOG.info("%s", response["SecretString"])
        LOG.info("Be careful with copy&pasting the secret value.")
    except (ClientError, BotoCoreError) as err:
        LOG.error(err)
        sys.exit(1)
