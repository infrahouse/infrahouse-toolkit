"""
.. topic:: ``ih-elastic cat repositories``

    A ``ih-elastic cat repositories`` subcommand.

    See ``ih-elastic cat repositories --help`` for more details.
"""

import logging

import click
from elasticsearch.client import CatClient

LOG = logging.getLogger()


@click.command(name="repositories")
@click.pass_context
def cmd_repositories(ctx):
    """
    Returns information about snapshot repositories registered in the cluster.
    """
    client = CatClient(ctx.obj["es"])
    LOG.info("\n%s", client.repositories(format=ctx.obj["format"], v=True))
