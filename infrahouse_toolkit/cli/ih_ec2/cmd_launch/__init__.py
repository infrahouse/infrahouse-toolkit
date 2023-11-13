"""
.. topic:: ``ih-ec2 launch``

    A ``ih-ec2 launch`` subcommand.

    See ``ih-ec2 launch`` for more details.
"""
import sys

import click
from tabulate import tabulate

from infrahouse_toolkit import LOG

SUPPORTED_UBUNTU_CODENAMES = ["jammy"]


def launch_ec2_instance(ec2_client, kwargs):
    """
    Launch EC2 instance.
    """
    response = ec2_client.run_instances(**kwargs)
    LOG.info("Successfully started instance %s.", response["Instances"][0]["InstanceId"])


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


def list_launch_templates(ec2_client):
    """
    Find and print information about available instance templates in a region.
    """
    response = ec2_client.describe_launch_templates()
    header = ["LaunchTemplateId", "LaunchTemplateName"]
    rows = []
    for launch_template in response["LaunchTemplates"]:
        rows.append([launch_template["LaunchTemplateId"], launch_template["LaunchTemplateName"]])
    print(tabulate(sorted(rows, key=lambda x: x[1]), headers=header, tablefmt="outline"))


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


@click.command(name="launch")
@click.option(
    "--subnet-id",
    help="Subnet ID where to launch the instance.",
    default=None,
)
@click.argument("launch_template", required=False)
@click.pass_context
def cmd_launch(ctx, subnet_id, launch_template):
    """
    Start an EC2 instance.
    """
    ec2_client = ctx.obj["ec2_client"]
    if not subnet_id:
        LOG.error("Please specify --subnet-id from following:")
        list_subnets(ec2_client)
        sys.exit(1)

    if launch_template:
        LOG.info("Using launch template %s", launch_template)
        kwargs = {"MinCount": 1, "MaxCount": 1, "LaunchTemplate": {"Version": "$Latest"}, "SubnetId": subnet_id}
        kwargs["LaunchTemplate"][
            "LaunchTemplateId" if launch_template.startswith("lt-") else "LaunchTemplateName"
        ] = launch_template
        launch_ec2_instance(ctx.obj["ec2_client"], kwargs)

    else:
        list_launch_templates(ec2_client)
