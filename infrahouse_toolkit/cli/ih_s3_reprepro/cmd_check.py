"""
.. topic:: ``ih-s3-reprepro check``

    A ``ih-s3-reprepro check`` subcommand.

    See ``ih-s3-reprepro check --help`` for more details.
"""

import click
from click import Context

from infrahouse_toolkit.cli.utils import execute, local_s3


@click.command(name="check")
@click.argument("codenames", nargs=-1)
@click.pass_context
def cmd_check(ctx: Context, codenames):
    """Check for all needed files to be registered properly."""
    bucket = ctx.parent.params["bucket"]
    role_arn = ctx.parent.params["role_arn"]
    with local_s3(bucket, role_arn, region=ctx.parent.params["aws_region"]) as path:
        cmd = [
            "reprepro",
            "-V",
            "-b",
            path,
            "check",
        ]
        cmd.extend(codenames)
        execute(cmd)
