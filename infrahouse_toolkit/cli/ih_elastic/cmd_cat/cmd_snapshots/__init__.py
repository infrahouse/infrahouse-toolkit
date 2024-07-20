"""
.. topic:: ``ih-elastic cat snapshots``

    A ``ih-elastic cat snapshots`` subcommand.

    See ``ih-elastic cat snapshots --help`` for more details.
"""

import logging

import click
from elasticsearch.client import CatClient

LOG = logging.getLogger()


@click.command(name="snapshots")
@click.pass_context
def cmd_snapshots(ctx):
    """
    Returns all snapshots.
    """
    client = CatClient(ctx.obj["es"])
    LOG.info("\n%s", client.snapshots(repository="_all", format=ctx.obj["format"], v=True))
