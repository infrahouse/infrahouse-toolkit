"""
.. topic:: ``ih-elastic``

    A ``ih-elastic`` command, Elasticsearch helper.

    See ``ih-elastic --help`` for more details.
"""
from logging import getLogger

import click

from infrahouse_toolkit.cli.ih_elastic.cmd_cluster_health import cmd_cluster_health
from infrahouse_toolkit.cli.ih_elastic.cmd_passwd import cmd_passwd
from infrahouse_toolkit.logging import setup_logging

LOG = getLogger()


@click.group(
    "ih-elastic",
)
@click.option(
    "--debug",
    help="Enable debug logging.",
    is_flag=True,
    default=False,
    show_default=True,
)
@click.pass_context
def ih_elastic(ctx, *args, **kwargs):  # pylint: disable=unused-argument
    """
    Elasticsearch helper.
    """
    setup_logging(debug=kwargs["debug"])


for cmd in [cmd_passwd, cmd_cluster_health]:
    # noinspection PyTypeChecker
    ih_elastic.add_command(cmd)
