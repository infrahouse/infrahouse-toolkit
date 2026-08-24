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
from infrahouse_toolkit.cli.ih_mysql.cmd_failover import cmd_failover
from infrahouse_toolkit.cli.ih_mysql.cmd_query_audit import cmd_query_audit

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
    "--quiet",
    help="Suppress informational and warning messages, output errors only. Overrides --debug.",
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
    # Three levels, with the useful one in the middle: --debug is everything,
    # no flag prints INFO and WARNING, --quiet drops to errors only. Warnings
    # here carry the safety findings, so suppressing them is opt-in.
    quiet = kwargs["quiet"]
    debug = kwargs["debug"] and not quiet
    setup_logging(debug=debug, quiet=quiet)

    ctx.obj = {
        "debug": debug,
        "aws_profile": kwargs["aws_profile"],
        "aws_region": kwargs["aws_region"],
    }


for cmd in [
    cmd_bootstrap,
    cmd_failover,
    cmd_query_audit,
]:
    # noinspection PyTypeChecker
    ih_mysql.add_command(cmd)
