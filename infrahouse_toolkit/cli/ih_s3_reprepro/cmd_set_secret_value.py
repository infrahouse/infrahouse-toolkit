"""
.. topic:: ``ih-s3-reprepro set-secret-value``

    A ``ih-s3-reprepro set-secret-value`` subcommand.

    See ``ih-s3-reprepro set-secret-value --help`` for more details.
"""
import sys
from logging import getLogger

import click
from botocore.exceptions import BotoCoreError, ClientError
from click import Context

from infrahouse_toolkit import DEFAULT_OPEN_ENCODING
from infrahouse_toolkit.cli.ih_s3_reprepro.aws import get_client

LOG = getLogger()


@click.command(name="set-secret-value")
@click.argument("secret_id")
@click.argument("path", nargs=-1)
@click.pass_context
def cmd_set_secret_value(ctx: Context, secret_id, path):
    """
    Set value to a secret.

    Optionally the value may be given via a local file specified by a path argument.

    \b
    ih-s3-reprepro ... set-secret-value mysecret /path/to/file_with_value

    if the path is omitted, a user will be prompt for the value.
    """
    role_arn = ctx.parent.params["role_arn"]
    try:
        client = get_client("secretsmanager", role_arn=role_arn, region=ctx.parent.params["aws_region"])
        if path:
            with open(path[0], encoding=DEFAULT_OPEN_ENCODING) as secret_value_desc:
                value = secret_value_desc.read()
        else:
            value = click.prompt("Enter a secret value and press ENTER", hide_input=True)

        LOG.debug("Secret value: %s", value)
        client.put_secret_value(SecretId=secret_id, SecretString=value)
        LOG.info("Value of %s is successfully set.", secret_id)

    except (ClientError, BotoCoreError) as err:
        LOG.error(err)
        sys.exit(1)
