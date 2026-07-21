"""
.. topic:: ``infrahouse_toolkit.cli.ih_openvpn.lib``

    Helpers shared by the ``ih-openvpn`` subcommands: parsing the easy-rsa
    certificate index and revoking a client certificate.
"""

import logging
import os
from collections import namedtuple
from subprocess import check_call

from infrahouse_toolkit import DEFAULT_OPEN_ENCODING

LOG = logging.getLogger()

#: Fallback OpenVPN configuration directory. Defined once and used in exactly
#: one place -- as the default of the ``ih-openvpn --config-dir`` option. Every
#: subcommand and helper takes the directory from ``ctx.obj["config_dir"]``
#: instead of reaching for this constant, so pointing the group at another
#: directory moves all of them together.
DEFAULT_CONFIG_DIR = "/etc/openvpn"


def index_path(config_dir):
    """
    Path of the easy-rsa certificate index inside a configuration directory.

    :param config_dir: OpenVPN configuration directory.
    :type config_dir: str
    :return: Path to ``pki/index.txt``.
    :rtype: str
    """
    return os.path.join(config_dir, "pki", "index.txt")


#: Status flag easy-rsa writes in column 0 of ``index.txt`` for a live
#: certificate. ``R`` means revoked and ``E`` expired.
STATUS_VALID = "V"

#: One row of the easy-rsa ``index.txt``.
IndexEntry = namedtuple("IndexEntry", ["status", "serial", "subject", "common_name"])


def parse_index(path):
    """
    Parse an easy-rsa ``index.txt`` into :py:class:`IndexEntry` records.

    The file is tab separated, one certificate per line::

        V<TAB>expiry<TAB>revoked<TAB>serial<TAB>filename<TAB>subject-dn

    Malformed lines are skipped with a warning rather than aborting: the index
    is shared state on EFS, and one unreadable row should not stop the rest of
    the certificates from being reconciled.

    :param path: Path to ``index.txt``, e.g. from :py:func:`index_path`.
    :type path: str
    :return: Parsed entries, in file order.
    :rtype: list(IndexEntry)
    """
    entries = []
    with open(path, encoding=DEFAULT_OPEN_ENCODING) as file_descriptor:
        for line_number, line in enumerate(file_descriptor.read().splitlines(), start=1):
            if not line.strip():
                continue
            cells = line.split("\t")
            if len(cells) < 6:
                LOG.warning("Skipping malformed %s line %d: %r", path, line_number, line)
                continue
            entries.append(
                IndexEntry(
                    status=cells[0],
                    serial=cells[3],
                    subject=cells[5],
                    common_name=extract_common_name(cells[5]),
                )
            )
    return entries


def extract_common_name(subject):
    """
    Pull the CN out of an OpenSSL subject DN.

    The DN carries the full set of easy-rsa request fields, e.g.
    ``/C=US/ST=California/O=InfraHouse Inc./CN=alice@infrahouse.com``, so the CN
    cannot be assumed to sit at any fixed position.

    :param subject: Subject DN as written in ``index.txt``.
    :type subject: str
    :return: The common name, or ``None`` when the DN carries no CN component.
    :rtype: str
    """
    for component in subject.split("/"):
        if component.startswith("CN="):
            return component[len("CN=") :]
    return None


def is_user_certificate(common_name):
    """
    Whether a common name identifies a directory user rather than infrastructure.

    This is a safety boundary, not a cosmetic filter. The PKI also contains the
    OpenVPN server's own certificate (``CN=server``), which is valid and will
    never appear in the Google directory. A reconciliation that treated every
    valid certificate as a candidate would therefore compute the server
    certificate as "belonging to no active user" and revoke it, taking the whole
    VPN down -- and it would do so on the first run of a fresh deployment, when
    no user certificates exist yet to dilute the diff.

    User certificates are minted by the portal with ``EASYRSA_REQ_CN`` set to the
    authenticated Google address, so every genuine user CN is an email address.
    Requiring an ``@`` excludes ``server`` and any other infrastructure
    certificate without needing to enumerate them.

    :param common_name: Common name from a certificate subject.
    :type common_name: str
    :return: True when the CN looks like a directory user's email address.
    :rtype: bool
    """
    return bool(common_name) and "@" in common_name


def valid_user_certificates(path):
    """
    Common names of live, user-owned certificates -- the revocation candidates.

    Filtered to valid (non-revoked, non-expired) certificates whose CN looks like
    a directory user, so infrastructure certificates can never enter the diff.
    See :py:func:`is_user_certificate`.

    :param path: Path to ``index.txt``, e.g. from :py:func:`index_path`.
    :type path: str
    :return: Common names of live user certificates.
    :rtype: set(str)
    """
    return {
        entry.common_name
        for entry in parse_index(path)
        if entry.status == STATUS_VALID and is_user_certificate(entry.common_name)
    }


def revoke_client(easyrsa_path, client, config_dir):
    """
    Revoke a client certificate and regenerate the CRL.

    OpenVPN re-reads the CRL on every new connection, so the revocation takes
    effect without restarting the service.

    ``config_dir`` is required rather than defaulted: every caller already holds
    the value from the ``ih-openvpn --config-dir`` option, and a default here
    would let a caller silently operate on ``/etc/openvpn`` while the operator
    pointed the group elsewhere.

    :param easyrsa_path: Path to the ``easyrsa`` executable.
    :type easyrsa_path: str
    :param client: Certificate common name, i.e. the user's email address.
    :type client: str
    :param config_dir: OpenVPN configuration directory holding ``vars`` and
        ``ca_passphrase``.
    :type config_dir: str
    :raise CalledProcessError: if easy-rsa fails; the CRL may then be stale.
        The caller decides how to surface that.
    """
    revoke_cmd = [easyrsa_path, f"--vars={config_dir}/vars", "revoke", client]
    update_cmd = [easyrsa_path, f"--vars={config_dir}/vars", "gen-crl"]
    for command in [revoke_cmd, update_cmd]:
        check_call(
            command,
            env={
                "EASYRSA_PASSIN": f"file:{config_dir}/ca_passphrase",
            },
        )
