"""
.. topic:: ``ih-openvpn revoke-client``

    A ``ih-openvpn revoke-client`` subcommand.

    See ``ih-openvpn revoke-client --help`` for more details.
"""

import logging
import sys
from subprocess import CalledProcessError

import click

from infrahouse_toolkit.cli.ih_openvpn.lib import revoke_client

LOG = logging.getLogger()


@click.command(name="revoke-client")
@click.argument("client")
@click.pass_context
def cmd_revoke_client(ctx: click.Context, *args, **kwargs):
    """
    Revoke client certificate from OpenVPN. Specify the client by email.

    \b

    ih-openvpn revoke-client aleks@infrahouse.com
    """
    LOG.debug("args = %s", args)
    LOG.debug("kwargs = %s", kwargs)
    LOG.debug(ctx.obj)
    try:
        revoke_client(ctx.obj["easyrsa_path"], kwargs["client"], ctx.obj["config_dir"])
        LOG.info("VPN access for client %s is revoked.", kwargs["client"])
    except CalledProcessError as err:
        LOG.error(err)
        update_cmd = [ctx.obj["easyrsa_path"], f"--vars={ctx.obj['config_dir']}/vars", "gen-crl"]
        LOG.info(
            "If you want to update the Certificate Revocation List, "
            "run command `sudo EASYRSA_PASSIN=file:%s/ca_passphrase %s`",
            ctx.obj["config_dir"],
            " ".join(update_cmd),
        )
        sys.exit(1)
