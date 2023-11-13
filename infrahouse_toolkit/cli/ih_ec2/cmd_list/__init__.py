"""
.. topic:: ``ih-ec2 list``

    A ``ih-ec2 list`` subcommand.

    See ``ih-ec2 list`` for more details.
"""
import sys

import click
from botocore.exceptions import ClientError
from tabulate import tabulate

from infrahouse_toolkit import LOG


def list_ec2_instances(ec2_client):
    """
    Print a summary about EC2 instances in a region.
    """
    response = ec2_client.describe_instances()
    instances = []
    header = ["InstanceId", "InstanceType", "PublicDnsName", "PublicIpAddress", "PrivateIpAddress"]
    for reservation in response["Reservations"]:
        for instance in reservation["Instances"]:
            name = None
            for tag in instance["Tags"]:
                if tag["Key"] == "Name":
                    name = tag["Value"]
            row = [name]
            for field in header:
                value = instance[field] if field in instance else ""
                row.append(value)
            row.append(instance["State"]["Name"])
            instances.append(row)

    print(tabulate(instances, headers=["Name"] + header + ["State"], tablefmt="outline"))


@click.command(name="list")
@click.pass_context
def cmd_list(ctx):
    """
    Start EC2 instance.
    """
    ec2_client = ctx.obj["ec2_client"]
    try:
        list_ec2_instances(ec2_client)
    except ClientError as err:
        LOG.exception(err)
        sys.exit(1)
