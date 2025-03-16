"""
.. topic:: ``ih-elastic cat snapshots``

    A ``ih-elastic cat snapshots`` subcommand.

    See ``ih-elastic cat snapshots --help`` for more details.
"""

import sys
from logging import getLogger

import click
from elastic_transport import ConnectionTimeout
from elasticsearch.client import CatClient

LOG = getLogger(__name__)


@click.command(name="snapshots")
@click.pass_context
def cmd_snapshots(ctx):
    """
    Returns all snapshots.
    """
    try:
        client: CatClient = CatClient(ctx.obj["es"])
        kwargs = {"repository": "_all", "format": ctx.obj["format"], "v": True, "request_timeout": 3600}
        # Disabling unexpected-keyword-arg because in elasticsearch 8.12.0 package version pylint fails
        # However, actual test proves `request_timeout` to be a valid argument.
        # 8.15.0 fixes this problem however the package is backwards incompatible.
        LOG.info(
            "\n%s",
            client.snapshots(**kwargs),  # pylint: disable=unexpected-keyword-arg
        )
    except ConnectionTimeout as err:
        LOG.exception(err)
        LOG.error("try to pass --request-timeout")
        sys.exit(1)
