"""
.. topic:: ``ih-s3-reprepro includedeb``

    A ``ih-s3-reprepro includedeb`` subcommand.

    See ``ih-s3-reprepro includedeb --help`` for more details.
"""

import sys
from logging import getLogger

import click
from botocore.exceptions import BotoCoreError, ClientError
from click import Context

from infrahouse_toolkit.cli.ih_s3_reprepro.utils import execute, repo_env

LOG = getLogger()


@click.command(name="includedeb")
@click.argument("codename")
@click.argument("deb_file")
@click.pass_context
def cmd_includedeb(ctx: Context, codename, deb_file):
    """
    Include the given binary package.

    Include the given binary Debian package (.deb) in the specified distribution,
    applying override information and guessing all values not given and guessable.
    """
    try:
        with repo_env(
            ctx.parent.params["bucket"],
            ctx.parent.params["role_arn"],
            ctx.parent.params["gpg_key_secret_id"],
            ctx.parent.params["gpg_passphrase_secret_id"],
            region=ctx.parent.params["aws_region"],
        ) as (path, gpg_home):
            execute(["reprepro", "-V", "-b", path, "--gnupghome", gpg_home, "includedeb", codename, deb_file])

    except (ClientError, BotoCoreError) as err:
        LOG.error(err)
        sys.exit(1)
