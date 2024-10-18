"""
.. topic:: ``ih-elastic cat nodes``

    A ``ih-elastic cat nodes`` subcommand.

    See ``ih-elastic cat nodes --help`` for more details.
"""

import json
from logging import getLogger

import click
from elasticsearch.client import CatClient, NodesClient

LOG = getLogger()


@click.command(name="nodes")
@click.argument("node_ip", required=False)
@click.pass_context
def cmd_nodes(ctx, **kwargs):
    """
    Lists nodes in a cluster.
    """
    if kwargs["node_ip"]:
        node_client = NodesClient(ctx.obj["es"])
        for node_id, node in node_client.info().raw["nodes"].items():
            if node["ip"] == kwargs["node_ip"]:
                LOG.info("Node %s", node_id)
                print(json.dumps(node, indent=4))

    else:
        client = CatClient(ctx.obj["es"])
        if ctx.obj["format"] == "json":
            print(json.dumps(client.nodes(format=ctx.obj["format"], v=True).raw, indent=4))
        else:
            print(client.nodes(format=ctx.obj["format"], v=True))
