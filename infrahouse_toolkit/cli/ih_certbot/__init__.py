"""
.. topic:: ``ih-certbot``

    A ``ih-certbot`` command, certbot wrapper

    See ``ih-certbot --help`` for more details.
"""
import sys
from logging import getLogger
from subprocess import CalledProcessError, check_call

import click

from infrahouse_toolkit.logging import setup_logging

LOG = getLogger()


@click.command(
    "ih-certbot",
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
@click.option(
    "--debug",
    help="Enable debug logging.",
    is_flag=True,
    default=False,
    show_default=True,
)
@click.pass_context
def ih_certbot(ctx, *args, **kwargs):  # pylint: disable=unused-argument
    """
    Tool to manage SSL certificates with the certbot client.
    It will run the certbot command packaged with the infrahouse-toolkit.

    To see the certbot's help run this:
    \b

    ih-certbot -- --help

    If infrahouse-toolkit is installed from a DEB package,
    the certbot command is also available in
    \b

    /opt/infrahouse-toolkit/embedded/bin/certbot
    """
    setup_logging(debug=kwargs["debug"])
    cmd = ["/opt/infrahouse-toolkit/embedded/bin/certbot"]
    cmd.extend(ctx.args)
    print(f"{cmd = }")
    try:
        check_call(cmd)
    except CalledProcessError as err:
        LOG.error(err)
        sys.exit(err.returncode)
