"""
.. topic:: ``ih-elastic``

    A ``ih-elastic`` command, Elasticsearch helper.

    See ``ih-elastic --help`` for more details.
"""

import socket
import sys
from logging import getLogger

import boto3
import click
from elasticsearch import Elasticsearch
from requests.auth import HTTPBasicAuth

from infrahouse_toolkit.cli.ih_elastic.cmd_api import cmd_api
from infrahouse_toolkit.cli.ih_elastic.cmd_cat import cmd_cat
from infrahouse_toolkit.cli.ih_elastic.cmd_cluster import cmd_cluster
from infrahouse_toolkit.cli.ih_elastic.cmd_cluster_health import cmd_cluster_health
from infrahouse_toolkit.cli.ih_elastic.cmd_passwd import cmd_passwd
from infrahouse_toolkit.cli.ih_elastic.cmd_security import cmd_security
from infrahouse_toolkit.cli.ih_elastic.cmd_snapshots import cmd_snapshots
from infrahouse_toolkit.cli.lib import get_elastic_password
from infrahouse_toolkit.logging import setup_logging

LOG = getLogger()


@click.group(
    "ih-elastic",
)
@click.option(
    "--debug",
    help="Enable debug logging.",
    is_flag=True,
    default=False,
    show_default=True,
)
@click.option(
    "--quiet",
    help="Suppress informational messages and output only warnings and errors.",
    is_flag=True,
    default=False,
    show_default=True,
)
@click.option(
    "--username",
    help="Username in Elasticsearch cluster.",
    default="elastic",
    show_default=True,
)
@click.option(
    "--password",
    help="Password for the Elasticsearch user. By default try to read it from puppet facts/AWS secretsmanager.",
    default=None,
    show_default=False,
)
@click.option(
    "--password-secret", help="AWS secretsmanager secret id with the password.", default=None, show_default=True
)
@click.option("--es-protocol", help="Elasticsearch protocol", default="http", show_default=True)
@click.option(
    "--es-host", help="Elasticsearch host", default=socket.gethostbyname(socket.gethostname()), show_default=True
)
@click.option("--es-port", help="Elasticsearch port", default=9200, show_default=True)
@click.option("--format", help="Output format", type=click.Choice(["text", "json", "cbor", "yaml", "smile"]))
@click.option(
    "--request-timeout", help="Timeout for HTTP requests in seconds.", default=10, show_default=True, type=click.INT
)
@click.version_option()
@click.pass_context
def ih_elastic(ctx, **kwargs):  # pylint: disable=unused-argument
    """
    Elasticsearch helper.
    """
    setup_logging(debug=kwargs["debug"], quiet=kwargs["quiet"])
    client = boto3.client("secretsmanager")
    password = kwargs["password"]

    if not password and not kwargs["password_secret"]:
        if kwargs["username"] == "elastic":
            password = get_elastic_password("elastic_secret")
        elif kwargs["username"] == "kibana_system":
            password = get_elastic_password("kibana_system_secret")

    if not password:
        if not kwargs["password_secret"]:
            LOG.error("You must specify either --password or --password-secret")
            sys.exit(1)

        response = client.get_secret_value(SecretId=kwargs["password_secret"])
        password = response["SecretString"]

    url = f"{kwargs['es_protocol']}://{kwargs['es_host']}:{kwargs['es_port']}"
    LOG.debug("Connecting to %s", url)
    ctx.obj = {
        "url": url,
        "auth": HTTPBasicAuth(kwargs["username"], password),
        "username": kwargs["username"],
        "password": password,
        "es": Elasticsearch(url, basic_auth=(kwargs["username"], password), request_timeout=kwargs["request_timeout"]),
        "format": kwargs["format"],
    }


for cmd in [cmd_passwd, cmd_cluster_health, cmd_snapshots, cmd_cat, cmd_cluster, cmd_security, cmd_api]:
    # noinspection PyTypeChecker
    ih_elastic.add_command(cmd)
