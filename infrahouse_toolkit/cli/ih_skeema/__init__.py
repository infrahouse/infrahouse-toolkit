"""
.. topic:: ``ih-skeema``

    A ``ih-skeema`` command, Skeema helpers

    See ``ih-skeema --help`` for more details.
"""

import json
import sys
from logging import getLogger
from subprocess import check_output

import boto3
import click

from infrahouse_toolkit import DEFAULT_ENCODING
from infrahouse_toolkit.cli.ih_secrets.cmd_get import get_secret
from infrahouse_toolkit.cli.ih_skeema.cmd_run import cmd_run
from infrahouse_toolkit.logging import setup_logging

LOG = getLogger()


@click.group(
    "ih-skeema",
)
@click.option(
    "--debug",
    help="Enable debug logging.",
    is_flag=True,
    default=False,
    show_default=True,
)
@click.option(
    "--skeema-path",
    help="Path to the skeema executable.",
    default="skeema",
    show_default=True,
)
@click.option(
    "--username",
    help="Username to connect to database host",
    default="root",
    show_default=True,
)
@click.option(
    "--password",
    help="Password for database user. By default, read from environment variable $MYSQL_PWD.",
    envvar="MYSQL_PWD",
    show_default=True,
)
@click.option(
    "--credentials-secret",
    help="If specified, read username and password from AWS secrets manager. "
    "The secret value must be a JSON with keys 'username' and 'password'.",
    default=None,
)
@click.pass_context
def ih_skeema(ctx, **kwargs):  # pylint: disable=unused-argument
    """
    Various Skeema (https://www.skeema.io/) helper commands. See ih-skeema --help for details.
    """
    setup_logging(debug=kwargs["debug"])
    try:
        out = check_output(
            [kwargs["skeema_path"], "--version"],
        )
        LOG.debug("Running skeema command: %s", out.decode(DEFAULT_ENCODING))
        username = kwargs["username"]
        password = kwargs["password"]

        if kwargs["credentials_secret"]:
            secretsmanager_client = boto3.client("secretsmanager")
            credentials = json.loads(get_secret(secretsmanager_client, kwargs["credentials_secret"]))
            username = credentials["username"]
            password = credentials["password"]

        ctx.obj = {
            "skeema_path": kwargs["skeema_path"],
            "username": username,
            "password": password,
        }

    except FileNotFoundError as err:
        LOG.error("Skeema executable not found: %s", err)
        LOG.error("Please install Skeema first or specify a skeema executable via --skeema-path.")
        sys.exit(1)


for cmd in [cmd_run]:
    # noinspection PyTypeChecker
    ih_skeema.add_command(cmd)
