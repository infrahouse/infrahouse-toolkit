"""
.. topic:: ``ih-elastic passwd``

    A ``ih-elastic passwd`` subcommand.

    See ``ih-elastic passwd --help`` for more details.
"""

from logging import getLogger

import boto3
import click
from elasticsearch.client import SecurityClient

LOG = getLogger(__name__)


@click.command(name="passwd")
@click.option("--username", help="Username of whose the password will be changed.", required=True)
@click.option("--new-password-secret", help="AWS secretsmanager secret id with a new password.", required=True)
@click.pass_context
def cmd_passwd(ctx, **kwargs):
    """
    Change password for Elasticsearch user.
    """
    client = boto3.client("secretsmanager")
    response = client.get_secret_value(SecretId=kwargs["new_password_secret"])
    new_password = response["SecretString"]

    client = SecurityClient(ctx.obj["es"])
    client.change_password(username=kwargs["username"], password=new_password)
    LOG.info("Successfully changed password for user %s.", kwargs["username"])
