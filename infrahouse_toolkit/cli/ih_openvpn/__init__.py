"""
.. topic:: ``ih-openvpn``

    A ``ih-openvpn`` command, openvpn helpers

    See ``ih-openvpn --help`` for more details.
"""

import sys
from logging import getLogger
from subprocess import check_output

import click
from infrahouse_core.logging import setup_logging

from infrahouse_toolkit import DEFAULT_ENCODING
from infrahouse_toolkit.cli.ih_openvpn.cmd_list import cmd_list_clients
from infrahouse_toolkit.cli.ih_openvpn.cmd_revoke import cmd_revoke_client
from infrahouse_toolkit.cli.ih_openvpn.cmd_sync_google_users import (
    cmd_sync_google_users,
)
from infrahouse_toolkit.cli.ih_openvpn.lib import DEFAULT_CONFIG_DIR

LOG = getLogger()


@click.group(
    "ih-openvpn",
)
@click.option(
    "--debug",
    help="Enable debug logging.",
    is_flag=True,
    default=False,
    show_default=True,
)
@click.option(
    "--easyrsa-path",
    help="Path to the easyrsa executable.",
    default="/usr/share/easy-rsa/easyrsa",
    show_default=True,
)
@click.option(
    "--config-dir",
    help="OpenVPN configuration directory, holding pki/, vars and ca_passphrase.",
    default=DEFAULT_CONFIG_DIR,
    show_default=True,
)
@click.pass_context
def ih_openvpn(ctx, **kwargs):  # pylint: disable=unused-argument
    """
    Various openvpn (https://openvpn.net/) helper commands. See ih-openvpn --help for details.
    """
    setup_logging(debug=kwargs["debug"])
    try:
        out = check_output(
            [kwargs["easyrsa_path"], "--version"],
        )
        LOG.debug("Running openvpn command: %s", out.decode(DEFAULT_ENCODING))
        ctx.obj = {
            "easyrsa_path": kwargs["easyrsa_path"],
            "config_dir": kwargs["config_dir"],
        }

    except FileNotFoundError as err:
        LOG.error("easyrsa executable not found: %s", err)
        LOG.error("Please install openvpn first or specify the easyrsa executable via --easyrsa-path.")
        sys.exit(1)


for cmd in [cmd_list_clients, cmd_revoke_client, cmd_sync_google_users]:
    # noinspection PyTypeChecker
    ih_openvpn.add_command(cmd)
