"""
.. topic:: ``ih-s3-reprepro dumpunreferenced``

    A ``ih-s3-reprepro dumpunreferenced`` subcommand.

    See ``ih-s3-reprepro dumpunreferenced --help`` for more details.
"""

import click
from click import Context

from infrahouse_toolkit.cli.utils import execute, local_s3


@click.command(name="dumpunreferenced")
@click.pass_context
def cmd_dumpunreferenced(ctx: Context):
    """Print a list of all filed believed to be in the pool, that are not known to be needed."""
    bucket = ctx.parent.params["bucket"]
    role_arn = ctx.parent.params["role_arn"]
    with local_s3(bucket, role_arn, region=ctx.parent.params["aws_region"]) as path:
        cmd = ["reprepro", "-V", "-b", path, "dumpunreferenced"]
        execute(cmd)
