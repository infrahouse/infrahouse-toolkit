"""
.. topic:: ``ih-s3-reprepro export``

    A ``ih-s3-reprepro export`` subcommand.

    See ``ih-s3-reprepro export --help`` for more details.
"""

import sys
from logging import getLogger

import click
from botocore.exceptions import BotoCoreError, ClientError
from click import Context

from infrahouse_toolkit.cli.utils import execute, repo_env

LOG = getLogger()


@click.command(name="export")
@click.argument("codename", nargs=-1)
@click.pass_context
def cmd_export(ctx: Context, codename):
    """
    Re-generate and re-sign the repository metadata.

    Runs ``reprepro export`` to rebuild the ``Release``, ``InRelease`` and
    ``Release.gpg`` index files and sign them with the key(s) named in
    ``conf/distributions`` (``SignWith:``). Unlike ``includedeb`` / ``remove``,
    this changes no packages, so it is the way to pick up a changed set of
    signing keys (e.g. during a GPG key rotation) without publishing a package.

    With no CODENAME, every distribution in ``conf/distributions`` is exported;
    otherwise only the given distribution(s) are.
    """
    try:
        with repo_env(
            ctx.parent.params["bucket"],
            ctx.parent.params["role_arn"],
            ctx.parent.params["gpg_key_secret_id"],
            ctx.parent.params["gpg_passphrase_secret_id"],
            region=ctx.parent.params["aws_region"],
        ) as (path, gpg_home):
            cmd = ["reprepro", "-V", "-b", path, "--gnupghome", gpg_home, "export"]
            cmd.extend(codename)
            execute(cmd)

    except (ClientError, BotoCoreError) as err:
        LOG.error(err)
        sys.exit(1)
