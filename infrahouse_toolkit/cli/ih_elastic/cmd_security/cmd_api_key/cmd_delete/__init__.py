"""
.. topic:: ``ih-elastic security api-key delete``

    A ``ih-elastic security api-key delete`` command.

    See ``ih-elastic security api-key delete --help`` for more details.
"""

import sys
from logging import getLogger

import click
from elasticsearch import NotFoundError
from elasticsearch.client import SecurityClient

LOG = getLogger(__name__)


@click.command(name="delete")
@click.argument("id")
@click.pass_context
def cmd_delete(ctx, **kwargs):
    """
    Create an API key.
    """
    client = SecurityClient(ctx.obj["es"])
    key_id = kwargs["id"]
    try:
        api_key = client.get_api_key(id=key_id)["api_keys"][0]
        client.invalidate_api_key(ids=[key_id])

        LOG.info(
            "API key %s:%s is invalidated. It will be fully deleted after the configured retention period.",
            api_key["id"],
            api_key["name"],
        )
    except NotFoundError:
        LOG.error("API key %s not found.", key_id)
        sys.exit(1)
