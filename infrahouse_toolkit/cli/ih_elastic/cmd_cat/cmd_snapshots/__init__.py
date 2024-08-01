"""
.. topic:: ``ih-elastic cat snapshots``

    A ``ih-elastic cat snapshots`` subcommand.

    See ``ih-elastic cat snapshots --help`` for more details.
"""
from logging import getLogger

import click
from elasticsearch.client import CatClient

LOG = getLogger(__name__)


@click.command(name="snapshots")
@click.pass_context
def cmd_snapshots(ctx):
    """
    Returns all snapshots.
    """
    client = CatClient(ctx.obj["es"])
    LOG.info("\n%s", client.snapshots(repository="_all", format=ctx.obj["format"], v=True))
