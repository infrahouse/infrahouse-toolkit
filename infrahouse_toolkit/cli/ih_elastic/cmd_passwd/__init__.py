"""
.. topic:: ``ih-elastic passwd``

    A ``ih-plan passwd`` subcommand.

    See ``ih-plan passwd --help`` for more details.
"""
import logging
import socket

import boto3
import click
import requests
from requests.auth import HTTPBasicAuth

LOG = logging.getLogger()


@click.command(name="passwd")
@click.option(
    "--admin-username",
    help="Username that will perform the change password operation",
    default="elastic",
    show_default=True,
)
@click.option("--admin-password-secret", help="AWS secretsmanager secret id with the admin password.", required=True)
@click.option("--username", help="Username of whose the password will be changed.", required=True)
@click.option("--new-password-secret", help="AWS secretsmanager secret id with a new password.", required=True)
@click.option("--es-protocol", help="Elasticsearch protocol", default="http", show_default=True)
@click.option(
    "--es-host", help="Elasticsearch host", default=socket.gethostbyname(socket.gethostname()), show_default=True
)
@click.option("--es-port", help="Elasticsearch port", default=9200, show_default=True)
def cmd_passwd(**kwargs):
    """
    Change password for Elasticsearch user.
    """
    client = boto3.client("secretsmanager")
    response = client.get_secret_value(SecretId=kwargs["admin_password_secret"])
    admin_password = response["SecretString"]
    response = client.get_secret_value(SecretId=kwargs["new_password_secret"])
    new_password = response["SecretString"]
    url = (
        f"{kwargs['es_protocol']}://{kwargs['es_host']}:{kwargs['es_port']}"
        f"/_security/user/{kwargs['username']}/_password"
    )
    LOG.debug("Connecting to %s", url)
    data = {"password": new_password}
    response = requests.post(
        url,
        headers={"Content-Type": "application/json; charset=utf-8"},
        json=data,
        auth=HTTPBasicAuth(kwargs["admin_username"], admin_password),
        timeout=60,
    )
    response.raise_for_status()
    LOG.info("Successfully changed password for user %s.", kwargs["username"])
