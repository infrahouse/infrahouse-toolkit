"""
.. topic:: ``ih-s3-reprepro remove``

    A ``ih-s3-reprepro remove`` subcommand.

    See ``ih-s3-reprepro remove --help`` for more details.
"""

import sys
from logging import getLogger

import click
from botocore.exceptions import BotoCoreError, ClientError
from click import Context

from infrahouse_toolkit.cli.utils import execute, repo_env

LOG = getLogger()


@click.command(name="remove")
@click.argument("codename")
@click.argument("package_name")
@click.pass_context
def cmd_remove(ctx: Context, codename, package_name):
    """Delete  all packages in the specified distribution, that have package name listed as argument."""
    try:
        with repo_env(
            ctx.parent.params["bucket"],
            ctx.parent.params["role_arn"],
            ctx.parent.params["gpg_key_secret_id"],
            ctx.parent.params["gpg_passphrase_secret_id"],
            region=ctx.parent.params["aws_region"],
        ) as (path, gpg_home):
            execute(["reprepro", "-V", "-b", path, "--gnupghome", gpg_home, "remove", codename, package_name])

    except (ClientError, BotoCoreError) as err:
        LOG.error(err)
        sys.exit(1)
