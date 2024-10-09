"""
.. topic:: ``ih-secrets get``

    A ``ih-secrets get`` subcommand.

    See ``ih-secrets get`` for more details.
"""

import sys
from logging import getLogger

import click
from botocore.exceptions import ClientError

from infrahouse_toolkit.aws import get_secret

LOG = getLogger(__name__)


@click.command(name="get")
@click.argument("secret")
@click.pass_context
def cmd_get(ctx, secret):
    """
    Get a secret value.
    """
    secretsmanager_client = ctx.obj["secretsmanager_client"]
    aws_config = ctx.obj["aws_config"]
    try:
        print(get_secret(secretsmanager_client, secret))
    except ClientError as err:
        LOG.exception(err)
        LOG.error("Try to run ih-secrets with --aws-profile option.")
        LOG.error("Available profiles:\n\t%s", "\n\t".join(aws_config.profiles))
        sys.exit(1)
