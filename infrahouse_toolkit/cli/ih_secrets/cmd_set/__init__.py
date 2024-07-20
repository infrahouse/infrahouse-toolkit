"""
.. topic:: ``ih-secrets set``

    A ``ih-secrets set`` subcommand.

    See ``ih-secrets set`` for more details.
"""

import sys
from logging import getLogger

import click
from botocore.exceptions import ClientError

from infrahouse_toolkit.cli.lib import read_from_file_or_prompt

LOG = getLogger(__name__)


@click.command(name="set")
@click.argument("secret")
@click.argument("path", nargs=-1)
@click.pass_context
def cmd_set(ctx, secret, path):
    """
    Set value to a secret.

    Optionally the value may be given via a local file specified by a path argument.

    \b
    ih-secrets set mysecret /path/to/file_with_value

    if the path is omitted, a user will be prompt for the value.
    """
    secretsmanager_client = ctx.obj["secretsmanager_client"]
    aws_config = ctx.obj["aws_config"]
    try:
        value = read_from_file_or_prompt(path[0] if path else None)
        LOG.debug("Secret value: %s", value)
        secretsmanager_client.put_secret_value(SecretId=secret, SecretString=value)
        LOG.info("Value of %s is successfully set.", secret)

    except ClientError as err:
        LOG.exception(err)
        LOG.error("Try to run ih-secrets with --aws-profile option.")
        LOG.error("Available profiles:\n\t%s", "\n\t".join(aws_config.profiles))
        sys.exit(1)
