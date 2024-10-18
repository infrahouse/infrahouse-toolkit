"""
.. topic:: ``ih-elastic api``

    A ``ih-elastic api`` subcommand.

    See ``ih-elastic cluster-health --help`` for more details.
"""

import json
import os
import sys
from json import JSONDecodeError
from logging import getLogger
from os import path as osp

import click
import requests

from infrahouse_toolkit import DEFAULT_OPEN_ENCODING

LOG = getLogger()


def _get_input(method, uri):
    ih_top = osp.expanduser("~/.infrahouse-toolkit")
    if not osp.exists(ih_top):
        os.mkdir(ih_top)
    tmpfile_name = osp.join(ih_top, f"ih-elastic-api-{method.lower()}-{''.join(e for e in uri if e.isalnum())}")
    click.edit(filename=tmpfile_name)
    os.chmod(tmpfile_name, 0o600)
    return open(tmpfile_name, encoding=DEFAULT_OPEN_ENCODING).read()


@click.command(name="api")
@click.option("-d", "--data", help="API call data.", is_flag=False, flag_value="editor", default=None)
@click.argument("METHOD", type=click.Choice(["GET", "HEAD", "POST", "PUT", "DELETE"]))
@click.argument("URI")
@click.pass_context
def cmd_api(ctx, **kwargs):
    """
    Execute a custom API call against the local Elasticsearch node.

    API documentation https://t.ly/-82Fw

    """
    method = kwargs["method"]
    url = ctx.obj["url"]
    uri = kwargs["uri"]
    request_kwargs = {"auth": ctx.obj["auth"], "headers": {"Content-Type": "application/json"}}
    if kwargs["data"] is not None:
        request_kwargs["data"] = _get_input(method, uri) if kwargs["data"] == "editor" else kwargs["data"]
        try:
            json.loads(request_kwargs["data"])
        except JSONDecodeError as err:
            LOG.error("Not a valid JSON:\n%s", request_kwargs["data"])
            LOG.error(err)
            sys.exit(1)

    full_url = f"{url}/{uri.lstrip('/')}"
    LOG.debug("Sending request %s", full_url)
    response = getattr(requests, method.lower())(full_url, **request_kwargs)
    try:
        print(json.dumps(response.json(), indent=4))
    except JSONDecodeError:
        print(response.text)
