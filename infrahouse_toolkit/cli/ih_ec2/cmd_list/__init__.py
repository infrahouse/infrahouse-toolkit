"""
.. topic:: ``ih-ec2 list``

    A ``ih-ec2 list`` subcommand.

    See ``ih-ec2 list`` for more details.
"""
import sys
from logging import getLogger
from pprint import pformat

import click
from botocore.exceptions import ClientError
from tabulate import tabulate

LOG = getLogger(__name__)


def list_ec2_instances(ec2_client):
    """
    Print a summary about EC2 instances in a region.
    """
    response = ec2_client.describe_instances()
    LOG.debug("describe_instances() = %s", pformat(response, indent=4))
    instances = []
    header = ["InstanceId", "InstanceType", "PublicDnsName", "PublicIpAddress", "PrivateIpAddress"]
    for reservation in response["Reservations"]:
        for instance in reservation["Instances"]:
            name = None
            for tag in instance.get("Tags") or []:
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
    List created EC2 instances.
    """
    ec2_client = ctx.obj["ec2_client"]
    aws_config = ctx.obj["aws_config"]
    try:
        list_ec2_instances(ec2_client)
    except ClientError as err:
        LOG.exception(err)
        LOG.info("Try to run ih-ec2 with --aws-profile option.")
        LOG.info("Available profiles:\n\t%s", "\n\t".join(aws_config.profiles))
        sys.exit(1)
