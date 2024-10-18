"""
.. topic:: ``ih-elastic security api-key create``

    A ``ih-elastic security api-key create`` command.

    See ``ih-elastic security api-key create --help`` for more details.
"""

import json
from logging import getLogger

import click
from elasticsearch.client import SecurityClient

LOG = getLogger(__name__)


@click.command(name="create")
@click.argument("name")
@click.pass_context
def cmd_create(ctx, name):
    """
    Create an API key.
    """
    client = SecurityClient(ctx.obj["es"])
    api_key = client.create_api_key(name=name)
    LOG.info("API key %s is created.", name)
    print(json.dumps(dict(api_key.body), indent=4))
