"""
.. topic:: ``ih-elastic snapshots restore``

    A ``ih-elastic snapshots restore`` subcommand.

    See ``ih-elastic snapshots restore --help`` for more details.
"""
import logging

import click
from elasticsearch.client import SnapshotClient

LOG = logging.getLogger()


@click.command(name="restore")
@click.argument("repository-name")
@click.argument("snapshot-name")
@click.pass_context
def cmd_restore(ctx, **kwargs):
    """
    Restores a snapshot in a repository.
    """
    client = SnapshotClient(ctx.obj["es"])
    client.restore(repository=kwargs["repository_name"], snapshot=kwargs["snapshot_name"])
