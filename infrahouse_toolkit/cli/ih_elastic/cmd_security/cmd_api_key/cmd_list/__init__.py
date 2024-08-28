"""
.. topic:: ``ih-elastic security api-key list``

    A ``ih-elastic security api-key list`` command.

    See ``ih-elastic security api-key list --help`` for more details.
"""
from logging import getLogger

import click
from elasticsearch.client import SecurityClient
from tabulate import tabulate

LOG = getLogger(__name__)


@click.command(name="list")
@click.pass_context
def cmd_list(ctx):
    """
    List API keys.
    """
    client = SecurityClient(ctx.obj["es"])
    header = [
        "id",
        "name",
        "type",
        "creation",
        "invalidated",
        "username",
        "realm",
        "realm_type",
        "metadata",
        "role_descriptors",
    ]
    api_keys = []
    for api_key in client.get_api_key()["api_keys"]:
        row = [api_key[h] for h in header]
        api_keys.append(row)

    print(tabulate(api_keys, headers=header, tablefmt="outline"))
