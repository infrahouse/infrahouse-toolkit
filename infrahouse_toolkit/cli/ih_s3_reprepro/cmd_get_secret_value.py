"""
.. topic:: ``ih-s3-reprepro get-secret-value``

    A ``ih-s3-reprepro get-secret-value`` subcommand.

    See ``ih-s3-reprepro get-secret-value --help`` for more details.
"""

import click
from click import Context

from infrahouse_toolkit import LOG
from infrahouse_toolkit.cli.ih_s3_reprepro.aws import get_client


@click.command(name="get-secret-value")
@click.argument("secret_id")
@click.pass_context
def cmd_get_secret_value(ctx: Context, secret_id):
    """
    Retrieve a secret value.
    """
    role_arn = ctx.parent.params["role_arn"]
    client = get_client("secretsmanager", role_arn=role_arn)
    response = client.get_secret_value(
        SecretId=secret_id,
    )
    LOG.info("%s", response["SecretString"])
    LOG.info("Be careful with copy&pasting the secret value.")
