"""
.. topic:: ``ih-openvpn revoke-client``

    A ``ih-openvpn revoke-client`` subcommand.

    See ``ih-openvpn revoke-client --help`` for more details.
"""

import logging
import sys
from subprocess import CalledProcessError, check_call

import click

LOG = logging.getLogger()


@click.command(name="revoke-client")
@click.argument("client")
@click.pass_context
def cmd_revoke_client(ctx, *args, **kwargs):
    """
    Revoke client certificate from OpenVPN. Specify the client by email.

    \b

    ih-openvpn revoke-client aleks@infrahouse.com
    """
    LOG.debug("args = %s", args)
    LOG.debug("kwargs = %s", kwargs)
    LOG.debug(ctx.obj)
    revoke_cmd = [ctx.obj["easyrsa_path"], "--vars=/etc/openvpn/vars", "revoke", kwargs["client"]]
    update_cmd = [ctx.obj["easyrsa_path"], "--vars=/etc/openvpn/vars", "gen-crl"]
    try:
        for command in [revoke_cmd, update_cmd]:
            check_call(
                command,
                env={
                    "EASYRSA_PASSIN": "file:/etc/openvpn/ca_passphrase",
                },
            )
        LOG.info("VPN access for client %s is revoked.", kwargs["client"])
    except CalledProcessError as err:
        LOG.error(err)
        LOG.info(
            "If you want to update the Certificate Revocation List, "
            "run command `sudo EASYRSA_PASSIN=file:/etc/openvpn/ca_passphrase %s`",
            " ".join(update_cmd),
        )
        sys.exit(1)
