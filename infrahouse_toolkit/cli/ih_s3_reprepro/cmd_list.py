"""
.. topic:: ``ih-s3-reprepro list``

    A ``ih-s3-reprepro list`` subcommand.

    See ``ih-s3-reprepro list --help`` for more details.
"""

import click
from click import Context

from infrahouse_toolkit.cli.utils import execute, local_s3


@click.command(name="list")
@click.argument("distribution")
@click.argument("package_name", nargs=-1)
@click.pass_context
def cmd_list(ctx: Context, distribution: str, package_name: str):
    """List all packages by the given name occurring in the given distribution."""
    bucket = ctx.parent.params["bucket"]
    role_arn = ctx.parent.params["role_arn"]
    with local_s3(bucket, role_arn, region=ctx.parent.params["aws_region"]) as path:
        cmd = ["reprepro", "-V", "-b", path, "list", distribution]
        cmd.extend(package_name)
        execute(cmd)
