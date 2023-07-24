"""
.. topic:: ``ih-s3-reprepro``

    A ``ih-s3-reprepro`` command..

    See ``ih-s3-reprepro --help`` for more details.
"""

import click

from infrahouse_toolkit.cli.ih_s3_reprepro.cmd_check import cmd_check
from infrahouse_toolkit.cli.ih_s3_reprepro.cmd_checkpool import cmd_checkpool
from infrahouse_toolkit.cli.ih_s3_reprepro.cmd_deleteunreferenced import (
    cmd_deleteunreferenced,
)
from infrahouse_toolkit.cli.ih_s3_reprepro.cmd_dumpunreferenced import (
    cmd_dumpunreferenced,
)
from infrahouse_toolkit.cli.ih_s3_reprepro.cmd_includedeb import cmd_includedeb
from infrahouse_toolkit.cli.ih_s3_reprepro.cmd_list import cmd_list
from infrahouse_toolkit.cli.ih_s3_reprepro.cmd_remove import cmd_remove
from infrahouse_toolkit.cli.ih_s3_reprepro.utils import DEPENDENCIES, check_dependencies


@click.group()
@click.option(
    "--bucket",
    help="AWS S3 bucket with a Debian repo",
    required=True,
)
@click.option("--role-arn", help="Assume this role for all AWS operations")
@click.option("--gpg-key-secret-id", help="AWS secrets manager secret name that stores a GPG private key.")
@click.option(
    "--gpg-passphrase-secret-id", help="AWS secrets manager secret name that stores a passphrase to the GPG key."
)
@click.pass_context
def ih_s3_reprepro(*args, **kwargs):  # pylint: disable=unused-argument
    """
    Tool to manage deb packages to a Debian repository hosted in an S3 bucket.
    """
    check_dependencies(DEPENDENCIES)


for cmd in [
    cmd_list,
    cmd_checkpool,
    cmd_check,
    cmd_remove,
    cmd_includedeb,
    cmd_dumpunreferenced,
    cmd_deleteunreferenced,
]:
    # noinspection PyTypeChecker
    ih_s3_reprepro.add_command(cmd)
