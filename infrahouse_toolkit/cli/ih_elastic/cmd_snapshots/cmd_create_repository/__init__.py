"""
.. topic:: ``ih-elastic snapshots create-repository``

    A ``ih-elastic snapshots create-repository`` subcommand.

    See ``ih-elastic snapshots create-repository --help`` for more details.
"""

from logging import getLogger

import click
from elasticsearch.client import SnapshotClient

LOG = getLogger(__name__)


@click.command(name="create-repository")
@click.argument("repository-name")
@click.argument("bucket-name")
@click.pass_context
def cmd_create_repository(ctx, **kwargs):
    """
    Creates a repository.
    """
    client = SnapshotClient(ctx.obj["es"])
    client.create_repository(
        name=kwargs["repository_name"],
        settings={
            "client": "default",
            "bucket": kwargs["bucket_name"],
        },
        type="s3",
    )
