"""
.. topic:: ``ih-ec2 launch-templates``

    A ``ih-ec2 launch-templates`` subcommand.

    See ``ih-ec2 launch-templates`` for more details.
"""

import sys
from logging import getLogger

import click
from botocore.exceptions import ClientError
from tabulate import tabulate

from infrahouse_toolkit.logging import setup_logging

LOG = getLogger()


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


@click.command(name="launch-templates")
@click.pass_context
def cmd_launch_templates(ctx):
    """
    Describe AWS launch-templates.
    """
    setup_logging(debug=ctx.obj["debug"])
    ec2_client = ctx.obj["ec2_client"]
    aws_config = ctx.obj["aws_config"]
    try:
        list_launch_templates(ec2_client)
    except ClientError as err:
        LOG.exception(err)
        LOG.info("Try to run ih-ec2 with --aws-profile option.")
        LOG.info("Available profiles:\n\t%s", "\n\t".join(aws_config.profiles))
        sys.exit(1)
