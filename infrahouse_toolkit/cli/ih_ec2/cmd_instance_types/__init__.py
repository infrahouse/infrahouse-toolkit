"""
.. topic:: ``ih-ec2 instance-types``

    A ``ih-ec2 instance-types`` subcommand.

    See ``ih-ec2 instance-types`` for more details.
"""

import sys
from logging import getLogger

import click
from botocore.exceptions import ClientError
from tabulate import tabulate

LOG = getLogger()


def list_instance_types(ec2_client):
    """
    Find and print supported instance types in a region.
    """

    def _format_storage_info(i_type):
        if field in i_type:
            disks = []
            for disk in i_type[field]["Disks"]:
                disks.append(f"{disk['Type']}: {disk['Count']} * {disk['SizeInGB']} GB")
            return f"{i_type[field]['TotalSizeInGB'] } GB: {' '.join(disks)}"
        return ""

    instance_types = []
    header = ["InstanceType", "ProcessorInfo", "MemoryInfo", "InstanceStorageInfo", "NetworkInfo"]
    next_token = None
    while True:
        kwargs = {}
        if next_token:
            kwargs["NextToken"] = next_token
        response = ec2_client.describe_instance_types(**kwargs)

        for instance_type in response["InstanceTypes"]:
            row = []
            for field in header:
                if field == "ProcessorInfo":
                    architectures = instance_type[field]["SupportedArchitectures"]
                    speed = (
                        instance_type[field]["SustainedClockSpeedInGhz"]
                        if "SustainedClockSpeedInGhz" in instance_type[field]
                        else ""
                    )
                    value = f"{', '.join(architectures)} {speed} GHz"

                elif field == "MemoryInfo":
                    value = f"{round(instance_type[field]['SizeInMiB'] / 1024) } GB"

                elif field == "InstanceStorageInfo":
                    value = _format_storage_info(instance_type)
                elif field == "NetworkInfo":
                    value = instance_type[field]["NetworkPerformance"]
                else:
                    value = instance_type[field] if field in instance_type else ""
                row.append(value)
            instance_types.append(row)

        if "NextToken" in response:
            next_token = response["NextToken"]
        else:
            break

    print(tabulate(sorted(instance_types, key=lambda x: x[0]), headers=header, tablefmt="outline"))


@click.command(name="instance-types")
@click.pass_context
def cmd_instance_types(ctx):
    """
    Describe AWS EC2 instance types.
    """
    ec2_client = ctx.obj["ec2_client"]
    try:
        list_instance_types(ec2_client)
    except ClientError as err:
        LOG.exception(err)
        sys.exit(1)
