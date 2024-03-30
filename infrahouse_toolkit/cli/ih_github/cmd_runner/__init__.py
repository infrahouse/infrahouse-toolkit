"""
.. topic:: ``ih-github runner``

    A ``ih-github runner`` subcommand.

    See ``ih-github run --help`` for more details.
"""
import logging

import boto3
import click

from infrahouse_toolkit.cli.ih_github.cmd_runner.cmd_deregister import cmd_deregister
from infrahouse_toolkit.cli.ih_github.cmd_runner.cmd_is_registered import (
    cmd_is_registered,
)
from infrahouse_toolkit.cli.ih_github.cmd_runner.cmd_list import cmd_list
from infrahouse_toolkit.cli.ih_github.cmd_runner.cmd_register import cmd_register
from infrahouse_toolkit.cli.ih_secrets.cmd_get import get_secret

LOG = logging.getLogger()


@click.group(
    name="runner",
)
@click.option("--github-token", help="Personal access token for GitHub.", envvar="GITHUB_TOKEN", show_default=True)
@click.option("--github-token-secret", help="Read GitHub token from AWS secret.")
@click.option(
    "--org",
    help="GitHub organization",
    required=True,
)
@click.pass_context
def cmd_runner(ctx, *args, **kwargs):
    """
    Manage self-hosted runners.

    """
    LOG.debug("args = %s", args)
    LOG.debug("kwargs = %s", kwargs)
    LOG.debug(ctx.args)
    if kwargs["github_token_secret"]:
        github_token = get_secret(boto3.client("secretsmanager"), kwargs["github_token_secret"])
    else:
        github_token = kwargs["github_token"]

    ctx.obj = {"github_token": github_token, "org": kwargs["org"]}


for cmd in [cmd_list, cmd_register, cmd_deregister, cmd_is_registered]:
    # noinspection PyTypeChecker
    cmd_runner.add_command(cmd)
