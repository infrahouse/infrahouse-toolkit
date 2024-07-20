"""
.. topic:: ``ih-ec2 subnets``

    A ``ih-ec2 subnets`` subcommand.

    See ``ih-ec2 subnets`` for more details.
"""

import sys
from logging import getLogger

import click
from botocore.exceptions import ClientError
from tabulate import tabulate

LOG = getLogger()


def get_vpc_name(ec2_client, vpc_id):
    """
    Given a vpc_id find out its name.
    """
    response = ec2_client.describe_vpcs(
        VpcIds=[
            vpc_id,
        ]
    )
    for tag in response["Vpcs"][0]["Tags"]:
        if tag["Key"] == "Name":
            return tag["Value"]

    return vpc_id


def list_subnets(ec2_client):
    """
    Find and print information about available subnets in a region.
    """
    response = ec2_client.describe_subnets()
    header = ["SubnetId", "Name", "Public", "CidrBlock", "VpcId", "VpcName"]
    rows = []
    vpc_names = {}
    for subnet in response["Subnets"]:
        row = []
        vpc_id = subnet["VpcId"]
        for field in header:
            if field == "Name":
                value = ""
                for tag in subnet["Tags"]:
                    if tag["Key"] == "Name":
                        value = tag["Value"]
            elif field == "VpcName":
                if vpc_id not in vpc_names:
                    vpc_names[vpc_id] = get_vpc_name(ec2_client, vpc_id)
                value = vpc_names[vpc_id]
            elif field == "Public":
                value = subnet["MapPublicIpOnLaunch"]
            else:
                value = subnet[field]
            row.append(value)
        rows.append(row)

    print(tabulate(sorted(rows, key=lambda x: x[1]), headers=header, tablefmt="outline"))


@click.command(name="subnets")
@click.pass_context
def cmd_subnets(ctx):
    """
    Describe AWS subnets.
    """
    ec2_client = ctx.obj["ec2_client"]
    aws_config = ctx.obj["aws_config"]
    try:
        list_subnets(ec2_client)
    except ClientError as err:
        LOG.exception(err)
        LOG.info("Try to run ih-ec2 with --aws-profile option.")
        LOG.info("Available profiles:\n\t%s", "\n\t".join(aws_config.profiles))
        sys.exit(1)
