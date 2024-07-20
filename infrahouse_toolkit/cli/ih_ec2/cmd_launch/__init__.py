"""
.. topic:: ``ih-ec2 launch``

    A ``ih-ec2 launch`` subcommand.

    See ``ih-ec2 launch`` for more details.
"""

import sys
from logging import getLogger

import click

from infrahouse_toolkit.cli.ih_ec2.cmd_launch_templates import list_launch_templates
from infrahouse_toolkit.cli.ih_ec2.cmd_subnets import list_subnets

LOG = getLogger()
SUPPORTED_UBUNTU_CODENAMES = ["jammy"]


def launch_ec2_instance(ec2_client, kwargs):
    """
    Launch EC2 instance.
    """
    response = ec2_client.run_instances(**kwargs)
    LOG.info("Successfully started instance %s.", response["Instances"][0]["InstanceId"])


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
        LOG.error(
            "A launch template isn't specified. "
            "Please pick one from the list and pass either the launch template name or id."
        )
        list_launch_templates(ec2_client)
