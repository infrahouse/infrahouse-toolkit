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

from infrahouse_toolkit.cli.utils import execute, repo_env

LOG = getLogger()


@click.command(name="includedeb")
@click.option(
    "--priority",
    help="Overrides the Debian package priority of inclusions.",
    type=click.Choice(["required", "important", "standard", "optional", "extra"]),
    default=None,
    show_default=True,
)
@click.argument("codename")
@click.argument("deb_file")
@click.pass_context
def cmd_includedeb(ctx: Context, priority, codename, deb_file):
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
            cmd = ["reprepro", "-V", "-b", path, "--gnupghome", gpg_home]
            if priority:
                cmd.extend(["--priority", priority])
            cmd.extend(["includedeb", codename, deb_file])
            execute(cmd)

    except (ClientError, BotoCoreError) as err:
        LOG.error(err)
        sys.exit(1)
