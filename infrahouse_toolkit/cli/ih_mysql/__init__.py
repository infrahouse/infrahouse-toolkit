"""
.. topic:: ``ih-mysql``

    A group of commands for MySQL/Percona Server management.
    Used by Puppet for bootstrap, user creation, and other MySQL management tasks.

    See ``ih-mysql --help`` for more details.
"""

from logging import getLogger

import click
from infrahouse_core.logging import setup_logging

from infrahouse_toolkit.aws.config import AWSConfig
from infrahouse_toolkit.cli.ih_mysql.cmd_bootstrap import cmd_bootstrap

LOG = getLogger(__name__)


@click.group()
@click.option(
    "--debug",
    help="Enable debug logging.",
    is_flag=True,
    default=False,
    show_default=True,
)
@click.option(
    "--verbose",
    help="Print INFO and WARNING level messages.",
    is_flag=True,
    default=False,
    show_default=True,
)
@click.option(
    "--aws-profile",
    help="AWS profile name for authentication.",
    type=click.Choice(AWSConfig().profiles),
    default=None,
    show_default=True,
)
@click.option(
    "--aws-region",
    help="AWS region to use.",
    type=click.Choice(AWSConfig().regions),
    show_default=True,
    default=None,
)
@click.version_option()
@click.pass_context
def ih_mysql(ctx, **kwargs):
    """MySQL/Percona Server management commands."""
    setup_logging(debug=kwargs["debug"], quiet=not kwargs["verbose"])

    ctx.obj = {
        "debug": kwargs["debug"],
        "aws_profile": kwargs["aws_profile"],
        "aws_region": kwargs["aws_region"],
    }


# noinspection PyTypeChecker
ih_mysql.add_command(cmd_bootstrap)
