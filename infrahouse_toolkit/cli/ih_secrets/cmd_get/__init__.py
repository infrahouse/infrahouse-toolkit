"""
.. topic:: ``ih-secrets get``

    A ``ih-secrets get`` subcommand.

    See ``ih-secrets get`` for more details.
"""

import sys
from logging import getLogger
from pprint import pformat

import click
from botocore.exceptions import ClientError

LOG = getLogger(__name__)


def get_secret(secretsmanager_client, secret_name):
    """
    Retrieve a value of a secret by its name.
    """
    response = secretsmanager_client.get_secret_value(
        SecretId=secret_name,
    )
    LOG.debug("get_secrets() = %s", pformat(response, indent=4))
    return response["SecretString"]


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
