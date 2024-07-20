"""
.. topic:: ``ih-github``

    A ``ih-github`` command, GitHub helpers

    See ``ih-github --help`` for more details.
"""

from logging import getLogger

import click

from infrahouse_toolkit.cli.ih_github.cmd_run import cmd_run
from infrahouse_toolkit.cli.ih_github.cmd_runner import cmd_runner
from infrahouse_toolkit.logging import setup_logging

LOG = getLogger()


@click.group(
    "ih-github",
)
@click.option(
    "--debug",
    help="Enable debug logging.",
    is_flag=True,
    default=False,
    show_default=True,
)
def ih_github(**kwargs):  # pylint: disable=unused-argument
    """
    Various GitHub helper commands. See ih-github --help for details.
    """
    setup_logging(debug=kwargs["debug"])


for cmd in [cmd_run, cmd_runner]:
    # noinspection PyTypeChecker
    ih_github.add_command(cmd)
