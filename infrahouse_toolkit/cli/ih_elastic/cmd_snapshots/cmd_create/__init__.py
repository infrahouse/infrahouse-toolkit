"""
.. topic:: ``ih-elastic snapshots create``

    A ``ih-elastic snapshots create`` subcommand.

    See ``ih-elastic snapshots create --help`` for more details.
"""

import json
from datetime import datetime, timezone
from logging import getLogger

import click
from elasticsearch import NotFoundError
from elasticsearch.client import ClusterClient, SnapshotClient

from infrahouse_toolkit import DEFAULT_OPEN_ENCODING

LOG = getLogger(__name__)


@click.command(name="create")
@click.option(
    "--bucket-name",
    help="If the repository doesn't exit, the tool will create one in an S# bucket with this name. "
    "By default, it will parse /etc/puppetlabs/facter/facts.d/custom.json "
    "and look for key .elasticsearch.snapshots_bucket",
    default=None,
)
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

    repo_name = kwargs["repository_name"]
    try:
        client.get_repository(name=repo_name)
    except NotFoundError:
        bucket = kwargs["bucket_name"]
        if bucket is None:
            with open("/etc/puppetlabs/facter/facts.d/custom.json", encoding=DEFAULT_OPEN_ENCODING) as f_desc:
                bucket = json.load(f_desc)["elasticsearch"]["snapshots_bucket"]

        client.create_repository(
            name=kwargs["repository_name"],
            settings={
                "client": "default",
                "bucket": bucket,
            },
            type="s3",
        )

    client.create(repository=repo_name, snapshot=f"{cluster_name}-{now}")
