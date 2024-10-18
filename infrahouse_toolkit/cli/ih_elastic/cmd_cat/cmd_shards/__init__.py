"""
.. topic:: ``ih-elastic cat shards``

    A ``ih-elastic cat shards`` subcommand.

    See ``ih-elastic cat shards --help`` for more details.
"""

import json
from logging import getLogger

import click
from elasticsearch.client import CatClient

LOG = getLogger(__name__)


@click.command(name="shards")
@click.pass_context
def cmd_shards(ctx):
    """
    Provides a detailed view of shard allocation on nodes.
    """
    client = CatClient(ctx.obj["es"])
    if ctx.obj["format"] == "json":
        print(json.dumps(client.shards(format=ctx.obj["format"], v=True).raw, indent=4))
    else:
        print(client.shards(format=ctx.obj["format"], v=True))
