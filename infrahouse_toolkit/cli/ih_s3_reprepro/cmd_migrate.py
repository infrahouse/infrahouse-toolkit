"""
.. topic:: ``ih-s3-reprepro migrate``

    A ``ih-s3-reprepro migrate`` subcommand.

    See ``ih-s3-reprepro migrate --help`` for more details.
"""

import sys
from logging import getLogger
from os import path as osp

import click
from botocore.exceptions import BotoCoreError, ClientError
from click import Context

from infrahouse_toolkit.cli.utils import execute, repo_env

LOG = getLogger()


@click.command(name="migrate")
@click.pass_context
def cmd_migrate(ctx: Context):
    """
    Upgrade reprepo database to 5.4.*.
    """
    try:
        with repo_env(
            ctx.parent.params["bucket"],
            ctx.parent.params["role_arn"],
            ctx.parent.params["gpg_key_secret_id"],
            ctx.parent.params["gpg_passphrase_secret_id"],
            region=ctx.parent.params["aws_region"],
        ) as (path, gpg_home):
            LOG.info("Removing existing database %s", osp.join(path, "db/packagenames.db"))
            execute(["rm", "-v", osp.join(path, "db/packagenames.db")])
            LOG.info("Checking the repo in %s", path)
            execute(["reprepro", "-V", "-b", path, "--gnupghome", gpg_home, "check"])
            LOG.info("Exporting the repo in %s", path)
            execute(["reprepro", "-V", "-b", path, "--gnupghome", gpg_home, "export"])

    except (ClientError, BotoCoreError) as err:
        LOG.error(err)
        sys.exit(1)
