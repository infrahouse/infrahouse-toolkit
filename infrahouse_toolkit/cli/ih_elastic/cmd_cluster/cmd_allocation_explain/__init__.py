"""
.. topic:: ``ih-elastic cluster allocation-explain``

    A ``ih-elastic cluster allocation-explain`` subcommand.

    See ``ih-elastic cluster allocation-explain --help`` for more details.
"""

import json
import sys
from logging import getLogger

import click
from elasticsearch import BadRequestError
from elasticsearch.client import ClusterClient

LOG = getLogger(__name__)


@click.command(name="allocation-explain")
@click.option(
    "--index",
    help="Specifies the name of the index that you would like an explanation for."
    " Run ih-elastic cat shards to get a list.",
    default=None,
    show_default=True,
)
@click.option(
    "--shard",
    help="Specifies the ID of the shard that you would like an explanation for."
    " Run ih-elastic cat shards to get a list.",
    default=None,
    show_default=True,
    type=click.INT,
)
@click.option(
    "--primary/--replica",
    help="If --primary, returns explanation for the primary shard for the given shard ID.",
    default=None,
    show_default=True,
    is_flag=True,
)
@click.pass_context
def cmd_allocation_explain(ctx, **kwargs):
    """
    Provides explanations for shard allocations in the cluster.
    """
    client = ClusterClient(ctx.obj["es"])
    try:
        ae_kwargs = {}
        for arg in ["index", "shard"]:
            if kwargs[arg]:
                ae_kwargs[arg] = kwargs[arg]
        if kwargs["primary"] is not None:
            ae_kwargs["primary"] = kwargs["primary"]

        LOG.info(json.dumps(client.allocation_explain(**ae_kwargs).body, indent=4))
    except BadRequestError as err:
        LOG.error(json.dumps(err.body, indent=4))
        sys.exit(1)
