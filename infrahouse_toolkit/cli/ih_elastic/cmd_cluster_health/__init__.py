"""
.. topic:: ``ih-elastic cluster-health``

    A ``ih-plan cluster-health`` subcommand.

    See ``ih-plan cluster-health --help`` for more details.
"""
import json
import logging
import socket
import sys

import boto3
import click
import requests
from requests.auth import HTTPBasicAuth

LOG = logging.getLogger()


@click.command(name="cluster-health")
@click.option(
    "--username",
    help="Username in Elasticsearch cluster.",
    default="elastic",
    show_default=True,
)
@click.option("--password", help="Password for the Elasticsearch user.", default=None, show_default=True)
@click.option(
    "--password-secret", help="AWS secretsmanager secret id with the password.", default=None, show_default=True
)
@click.option("--es-protocol", help="Elasticsearch protocol", default="http", show_default=True)
@click.option(
    "--es-host", help="Elasticsearch host", default=socket.gethostbyname(socket.gethostname()), show_default=True
)
@click.option("--es-port", help="Elasticsearch port", default=9200, show_default=True)
def cmd_cluster_health(**kwargs):
    """
    Connect to Elasticsearch host and print the cluster health.
    """
    client = boto3.client("secretsmanager")
    password = kwargs["password"]
    if not password:
        if not kwargs["password_secret"]:
            LOG.error("You must specify either --password or --password-secret")
            sys.exit(1)

        response = client.get_secret_value(SecretId=kwargs["password_secret"])
        password = response["SecretString"]

    url = f"{kwargs['es_protocol']}://{kwargs['es_host']}:{kwargs['es_port']}/_cluster/health"
    LOG.debug("Connecting to %s", url)
    response = requests.get(url, auth=HTTPBasicAuth(kwargs["username"], password), timeout=60)
    response.raise_for_status()
    LOG.info("%s", json.dumps(response.json(), indent=4))
