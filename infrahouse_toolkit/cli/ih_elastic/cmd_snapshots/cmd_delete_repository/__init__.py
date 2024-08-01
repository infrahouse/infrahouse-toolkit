"""
.. topic:: ``ih-elastic snapshots delete-repository``

    A ``ih-elastic snapshots delete-repository`` subcommand.

    See ``ih-elastic snapshots delete-repository --help`` for more details.
"""
from logging import getLogger

import click
from elasticsearch.client import SnapshotClient

LOG = getLogger(__name__)


@click.command(name="delete-repository")
@click.argument("repository-name")
@click.pass_context
def cmd_delete_repository(ctx, **kwargs):
    """
    Deletes a repository.
    """
    client = SnapshotClient(ctx.obj["es"])
    client.delete_repository(
        name=kwargs["repository_name"],
    )
