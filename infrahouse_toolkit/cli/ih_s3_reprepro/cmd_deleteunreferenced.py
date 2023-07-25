"""
.. topic:: ``ih-s3-reprepro deleteunreferenced``

    A ``ih-s3-reprepro deleteunreferenced`` subcommand.

    See ``ih-s3-reprepro deleteunreferenced --help`` for more details.
"""

import click
from click import Context

from infrahouse_toolkit.cli.ih_s3_reprepro.utils import execute, local_s3


@click.command(name="deleteunreferenced")
@click.pass_context
def cmd_deleteunreferenced(ctx: Context):
    """Remove all known files (and forget them) in the pool not marked to be needed by anything."""
    bucket = ctx.parent.params["bucket"]
    role_arn = ctx.parent.params["role_arn"]
    with local_s3(bucket, role_arn, region=ctx.parent.params["aws_region"]) as path:
        cmd = ["reprepro", "-V", "-b", path, "deleteunreferenced"]
        execute(cmd)
