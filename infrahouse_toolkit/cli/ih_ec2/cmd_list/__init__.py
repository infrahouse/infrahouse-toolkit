"""
.. topic:: ``ih-ec2 list``

    A ``ih-ec2 list`` subcommand.

    See ``ih-ec2 list`` for more details.
"""

import json
import sys
from logging import getLogger
from pprint import pformat

import click
from botocore.exceptions import ClientError
from tabulate import tabulate

from infrahouse_toolkit.logging import setup_logging

LOG = getLogger(__name__)


def list_ec2_instances(ec2_client, fields=None, tag_filter=None, comma_separated=False):
    """
    Print a summary about EC2 instances in a region.
    """
    kwargs = {}
    if tag_filter:
        kwargs["Filters"] = tag_filter

    response = ec2_client.describe_instances(**kwargs)
    LOG.debug("describe_instances() = %s", pformat(response, indent=4))
    instances = []
    header = ["PrivateIpAddress", "InstanceId", "InstanceType"]
    fields = {} if fields is None else fields
    header.extend([k for k, v in fields.items() if v])
    for reservation in response["Reservations"]:
        for instance in reservation["Instances"]:
            name = None
            for tag in instance.get("Tags") or []:
                if tag["Key"] == "Name":
                    name = tag["Value"]
            row = [name]
            for field in header:
                value = instance[field] if field in instance else ""
                if field == "Tags":
                    value = json.dumps(
                        dict(
                            sorted(
                                {tag.get("Key"): tag.get("Value") for tag in value if tag.get("Key") != "Name"}.items()
                            )
                        ),
                        indent=4,
                    )
                row.append(value)
            row.append(instance["State"]["Name"])
            instances.append(row)

    if comma_separated:
        print(",".join([i[1] for i in instances]))
    else:
        print(
            tabulate(
                sorted(instances),
                headers=["Name"] + header + ["State"],
                tablefmt="grid" if fields["Tags"] else "outline",
            )
        )


@click.command(
    name="list",
    context_settings={
        "ignore_unknown_options": True,
        "allow_extra_args": True,
    },
)
@click.option(
    "--public-dns-name",
    "PublicDnsName",
    help="Show public DNS name.",
    is_flag=True,
    default=False,
)
@click.option(
    "--public-ip-address",
    "PublicIpAddress",
    help="Show public IP address.",
    is_flag=True,
    default=False,
)
@click.option(
    "-c",
    help="Output a comma-separated list instead of table.",
    is_flag=True,
    default=False,
)
@click.option(
    "--tags",
    "Tags",
    help="Show tags.",
    is_flag=True,
    default=False,
)
@click.pass_context
def cmd_list(ctx, **kwargs):
    """
    List created EC2 instances.

    By default, it will show instances' Name, PrivateIpAddress, InstanceId, InstanceType, and State.

    To display the instance's public DNS name or IP address, use options --public-dns-name,
    --public-ip-address respectively.

    Option --tags will show instance's tags.

    You can use tag names to filter output. For instance, option --service will show instances
    that have a tag 'service'. The same option with a value e.g. --service=vpn-portal will show instances
    that have a tag 'service' and its value 'vpn-portal'. Use comma separated service name to display more
    than one service. e.g. --service=elastic,elastic-kibana.
    """
    setup_logging(debug=ctx.obj["debug"], quiet=not kwargs["c"])

    ec2_client = ctx.obj["ec2_client"]
    aws_config = ctx.obj["aws_config"]
    tag_filter = []
    for arg in ctx.args:
        arg = arg.lstrip("--")
        split = arg.split("=")
        if len(split) < 2:
            name = "tag-key"
            values = [split[0]]
        else:
            name = f"tag:{split[0]}"
            values = list(split[1].split(","))

        tag_filter.append({"Name": name, "Values": values})

    try:
        comma_separated = kwargs.pop("c")
        list_ec2_instances(ec2_client, kwargs, tag_filter, comma_separated=comma_separated)
    except ClientError as err:
        LOG.exception(err)
        LOG.info("Try to run ih-ec2 with --aws-profile option.")
        LOG.info("Available profiles:\n\t%s", "\n\t".join(aws_config.profiles))
        sys.exit(1)
