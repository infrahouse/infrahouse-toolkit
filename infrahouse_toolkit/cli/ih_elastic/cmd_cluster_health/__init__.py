"""
.. topic:: ``ih-elastic cluster-health``

    A ``ih-elastic cluster-health`` subcommand.

    See ``ih-elastic cluster-health --help`` for more details.
"""

import json
from logging import getLogger

import click
from elasticsearch.client import ClusterClient

LOG = getLogger(__name__)


@click.command(name="cluster-health")
@click.pass_context
def cmd_cluster_health(ctx):
    """
    Connect to Elasticsearch host and print the cluster health.
    """
    client = ClusterClient(ctx.obj["es"])
    health = client.health()
    LOG.info(json.dumps(health.body, indent=4))
