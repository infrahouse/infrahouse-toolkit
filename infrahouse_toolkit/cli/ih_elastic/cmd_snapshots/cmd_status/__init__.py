"""
.. topic:: ``ih-elastic snapshots status``

    A ``ih-elastic snapshots status`` subcommand.

    See ``ih-elastic snapshots status --help`` for more details.
"""

import json
from logging import getLogger

import click
from elasticsearch.client import SnapshotClient

LOG = getLogger(__name__)


@click.command(name="status")
@click.argument("repository")
@click.argument("snapshot")
@click.pass_context
def cmd_status(ctx, **kwargs):
    """
    Returns information about the status of a snapshot.
    """
    client = SnapshotClient(ctx.obj["es"])
    print(json.dumps(client.status(repository=kwargs["repository"], snapshot=kwargs["snapshot"]).body, indent=4))
