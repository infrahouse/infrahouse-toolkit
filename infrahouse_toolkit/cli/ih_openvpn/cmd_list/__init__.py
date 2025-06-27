"""
.. topic:: ``ih-openvpn list-clients``

    A ``ih-openvpn list-clients`` subcommand.

    See ``ih-openvpn list-clients --help`` for more details.
"""

import json
import logging

import click
from tabulate import tabulate

from infrahouse_toolkit import DEFAULT_OPEN_ENCODING

LOG = logging.getLogger()


@click.command(name="list-clients")
@click.pass_context
def cmd_list_clients(ctx, *args, **kwargs):
    """
    List OpenVPN clients.
    """
    LOG.debug("args = %s", args)
    LOG.debug("kwargs = %s", kwargs)
    LOG.debug(ctx.args)
    header = ["Valid", "Created at", "Revoked at", "Serial", "State", "Certificate"]
    users = []
    with open("/etc/openvpn/pki/index.txt", encoding=DEFAULT_OPEN_ENCODING) as fp:
        lines = fp.read().splitlines()
        for line in lines:
            cells = line.split("\t")
            certificate = json.dumps(cells[5].split("/")[1:], indent=4)
            users.append(
                [
                    cells[0],  # Valid
                    cells[1],  # Created at
                    cells[2],  # Revoked at
                    cells[3],  # Serial
                    certificate,  # Certificate
                ]
            )

    print(
        tabulate(
            sorted(users),
            headers=header,
            tablefmt="grid",
        )
    )
