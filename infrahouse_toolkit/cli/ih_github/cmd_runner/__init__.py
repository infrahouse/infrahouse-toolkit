"""
.. topic:: ``ih-github runner``

    A ``ih-github runner`` subcommand.

    See ``ih-github run --help`` for more details.
"""
import logging

import click

from infrahouse_toolkit.cli.ih_github.cmd_runner.cmd_deregister import cmd_deregister
from infrahouse_toolkit.cli.ih_github.cmd_runner.cmd_list import cmd_list
from infrahouse_toolkit.cli.ih_github.cmd_runner.cmd_register import cmd_register

LOG = logging.getLogger()


@click.group(
    name="runner",
)
@click.option("--github-token", help="Personal access token for GitHub.", envvar="GITHUB_TOKEN")
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
    ctx.obj = {"github_token": kwargs["github_token"], "org": kwargs["org"]}


for cmd in [cmd_list, cmd_register, cmd_deregister]:
    # noinspection PyTypeChecker
    cmd_runner.add_command(cmd)
