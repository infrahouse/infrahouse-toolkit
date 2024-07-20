"""
.. topic:: ``ih-plan``

    A group of commands to work with a Terraform plan file.
    The command can upload the plan to an S3 bucket, download it, and remove.

    See ``ih-plan --help`` for more details.
"""

import click

from infrahouse_toolkit.cli.ih_plan.cmd_download import cmd_download
from infrahouse_toolkit.cli.ih_plan.cmd_min_permissions import cmd_min_permissions
from infrahouse_toolkit.cli.ih_plan.cmd_publish import cmd_publish
from infrahouse_toolkit.cli.ih_plan.cmd_remove import cmd_remove
from infrahouse_toolkit.cli.ih_plan.cmd_upload import cmd_upload
from infrahouse_toolkit.cli.lib import DEFAULT_TF_BACKEND_FILE


@click.group()
@click.option(
    "--bucket",
    help="AWS S3 bucket name to upload/download the plan. "
    "By default, parse Terraform backend configuration (see --tf-backend-file)"
    " in the current directory.",
    default=None,
)
@click.option(
    "--aws-assume-role-arn",
    help="ARN of a role the AWS client should assume.",
    default=None,
)
@click.option(
    "--tf-backend-file",
    help="File with Terraform backend configuration.",
    default=DEFAULT_TF_BACKEND_FILE,
    show_default=True,
)
@click.version_option()
@click.pass_context
def ih_plan(ctx, bucket, aws_assume_role_arn, tf_backend_file):
    """Terraform plan helpers."""
    ctx.obj = {"aws_assume_role_arn": aws_assume_role_arn, "bucket": bucket, "tf_backend_file": tf_backend_file}


for cmd in [cmd_upload, cmd_download, cmd_remove, cmd_publish, cmd_min_permissions]:
    # noinspection PyTypeChecker
    ih_plan.add_command(cmd)
