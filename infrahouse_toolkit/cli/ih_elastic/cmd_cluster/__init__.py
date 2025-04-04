"""
.. topic:: ``ih-elastic cat``

    A ``ih-elastic cat`` subcommand.

    See ``ih-elastic cat --help`` for more details.
"""

from logging import getLogger

import click

from infrahouse_toolkit.cli.ih_elastic.cmd_cluster.cmd_allocation_explain import (
    cmd_allocation_explain,
)
from infrahouse_toolkit.cli.ih_elastic.cmd_cluster.cmd_commision_node import (
    cmd_commission_node,
)
from infrahouse_toolkit.cli.ih_elastic.cmd_cluster.cmd_decommision_node import (
    cmd_decommission_node,
)

LOG = getLogger(__name__)


@click.group(name="cluster")
def cmd_cluster():
    """
    Cluster level operations.
    """


for cmd in [cmd_allocation_explain, cmd_decommission_node, cmd_commission_node]:
    # noinspection PyTypeChecker
    cmd_cluster.add_command(cmd)
