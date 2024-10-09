"""
.. topic:: ``ih-s3-reprepro checkpool``

    A ``ih-s3-reprepro checkpool`` subcommand.

    See ``ih-s3-reprepro checkpool --help`` for more details.
"""

import click
from click import Context

from infrahouse_toolkit.cli.utils import execute, local_s3


@click.command(name="checkpool")
@click.pass_context
def cmd_checkpool(ctx: Context):
    """Check if all files in the pool are still in proper shape."""
    bucket = ctx.parent.params["bucket"]
    role_arn = ctx.parent.params["role_arn"]
    with local_s3(bucket, role_arn, region=ctx.parent.params["aws_region"]) as path:
        execute(["reprepro", "-V", "-b", path, "checkpool"])
