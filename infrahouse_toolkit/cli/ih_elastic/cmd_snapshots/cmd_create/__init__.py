"""
.. topic:: ``ih-elastic snapshots create``

    A ``ih-elastic snapshots create`` subcommand.

    See ``ih-elastic snapshots create --help`` for more details.
"""
import logging
from datetime import datetime, timezone

import click
from elasticsearch.client import ClusterClient, SnapshotClient

LOG = logging.getLogger()


@click.command(name="create")
@click.argument("repository-name")
@click.pass_context
def cmd_create(ctx, **kwargs):
    """
    Creates a snapshot in a repository.
    """
    client = ClusterClient(ctx.obj["es"])
    cluster_name = client.info(target="_all")["cluster_name"]
    client = SnapshotClient(ctx.obj["es"])
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S.%f")

    client.create(repository=kwargs["repository_name"], snapshot=f"{cluster_name}-{now}")
