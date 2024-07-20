"""
.. topic:: ``ih-registry``

    A group of commands to work with InfraHouse Terraform registry.

    See ``ih-registry --help`` for more details.
"""

from logging import getLogger

import click

from infrahouse_toolkit.cli.ih_registry.cmd_upload import cmd_upload
from infrahouse_toolkit.logging import setup_logging

LOG = getLogger()


@click.group()
@click.option(
    "--debug",
    help="Enable debug logging.",
    is_flag=True,
    default=False,
    show_default=True,
)
@click.version_option()
@click.pass_context
def ih_registry(ctx, **kwargs):
    """InfraHouse Terraform Registry helpers."""
    setup_logging(debug=kwargs["debug"])
    ctx.obj = {"debug": kwargs["debug"]}


for cmd in [cmd_upload]:
    # noinspection PyTypeChecker
    ih_registry.add_command(cmd)
