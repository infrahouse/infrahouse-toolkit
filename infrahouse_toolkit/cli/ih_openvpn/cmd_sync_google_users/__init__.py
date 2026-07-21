"""
.. topic:: ``ih-openvpn sync-google-users``

    A ``ih-openvpn sync-google-users`` subcommand.

    See ``ih-openvpn sync-google-users --help`` for more details.
"""

import logging
import os
import sys
from subprocess import CalledProcessError

import click

from infrahouse_toolkit.cli.ih_openvpn.lib import (
    index_path,
    revoke_client,
    valid_user_certificates,
)

LOG = logging.getLogger()

#: ``EX_CONFIG`` from sysexits.h. Signals "the Google side is not configured
#: yet" as distinct from "this is broken". The Puppet wrapper that drives this
#: command on a cron treats 78 as *not ready* -- it logs and exits 0 -- so a
#: fleet that has not yet had domain-wide delegation authorized stays quiet
#: instead of mailing an operator daily. Any other non-zero status is reported
#: as a genuine failure. Changing this value breaks that contract; see
#: puppet-code ``modules/profile/templates/openvpn_server/google-user-sync.sh.erb``.
EX_CONFIG = 78

DIRECTORY_SCOPE = "https://www.googleapis.com/auth/admin.directory.user.readonly"
CLOUD_PLATFORM_SCOPE = "https://www.googleapis.com/auth/cloud-platform"


def _directory_client(service_account, admin_subject):
    """
    Build a Directory API client authenticated keylessly for ``admin_subject``.

    Application Default Credentials resolve to the Workload Identity Federation
    config that Terraform writes, which sources an AWS instance identity from
    IMDS. That federated identity impersonates the directory-reader service
    account, which in turn uses domain-wide delegation to act as
    ``admin_subject``. No service-account key exists anywhere.

    :param service_account: Email of the directory-reader service account.
    :type service_account: str
    :param admin_subject: Workspace admin the service account impersonates.
    :type admin_subject: str
    :return: A ready ``admin`` / ``directory_v1`` client.
    :raise GoogleNotConfigured: if credentials cannot be resolved yet.
    """
    # Imported lazily so that the rest of ih-openvpn keeps working on hosts
    # without the google libraries installed. The disable covers the whole block
    # because black rewrites trailing per-line comments into the parentheses,
    # where pylint no longer honours them.
    # pylint: disable=import-outside-toplevel
    import google.auth
    from google.auth import impersonated_credentials
    from google.auth.exceptions import DefaultCredentialsError
    from googleapiclient.discovery import build

    try:
        source_credentials, _ = google.auth.default(scopes=[CLOUD_PLATFORM_SCOPE])
    except DefaultCredentialsError as err:
        # No usable Application Default Credentials: the Terraform-written
        # credential config is missing or malformed, or IMDS is unreachable so
        # the external_account source cannot produce an AWS identity. All are
        # states that precede a finished deployment, not regressions.
        raise GoogleNotConfigured(f"no usable application default credentials: {err}") from err

    delegated = impersonated_credentials.Credentials(
        source_credentials=source_credentials,
        target_principal=service_account,
        target_scopes=[DIRECTORY_SCOPE],
        subject=admin_subject,
    )
    return build("admin", "directory_v1", credentials=delegated, cache_discovery=False)


def get_active_directory_users(service_account, admin_subject):
    """
    List the primary email addresses of all non-suspended Google Workspace users.

    :param service_account: Email of the directory-reader service account.
    :type service_account: str
    :param admin_subject: Workspace admin the service account impersonates.
    :type admin_subject: str
    :return: Primary email addresses of active users, lowercased.
    :rtype: set(str)
    :raise GoogleNotConfigured: if the Google side is not set up yet.
    :raise HttpError: on a directory API error that is not a setup problem.
    """
    # pylint: disable=import-outside-toplevel
    from google.auth.exceptions import RefreshError
    from googleapiclient.errors import HttpError

    directory = _directory_client(service_account, admin_subject)

    users = set()
    page_token = None
    try:
        while True:
            # query="isSuspended=false" would push the filter server-side, but
            # listing everyone and filtering here means a user missing from the
            # response for any reason is never mistaken for a suspended one.
            # googleapiclient builds resource methods dynamically from the
            # discovery document, so .users() is invisible to static analysis.
            response = (
                directory.users()  # pylint: disable=no-member
                .list(customer="my_customer", maxResults=500, projection="basic", pageToken=page_token)
                .execute()
            )
            for user in response.get("users", []):
                if not user.get("suspended", False):
                    users.add(user["primaryEmail"].lower())
            page_token = response.get("nextPageToken")
            if not page_token:
                break
    except RefreshError as err:
        # Domain-wide delegation has not been authorized for this service
        # account's client id, so the token exchange is rejected outright.
        raise GoogleNotConfigured(f"domain-wide delegation is not authorized: {err}") from err
    except HttpError as err:
        # 403 typically means delegation exists but the directory scope was not
        # granted; 401 that the subject is not a real admin. Both are "not
        # configured yet", not a regression, so they must not page anyone.
        if err.resp.status in (401, 403):
            raise GoogleNotConfigured(f"directory API rejected the request ({err.resp.status}): {err}") from err
        raise

    return users


class GoogleNotConfigured(Exception):
    """
    The Google Workspace side of the integration is not set up yet.

    Raised for conditions an operator is expected to hit *before* finishing
    setup -- delegation not authorized, scope not granted, subject not an admin
    -- and never for failures that appear after a working deployment. The
    command maps it to :py:const:`EX_CONFIG`.
    """


@click.command(name="sync-google-users")
@click.option(
    "--service-account",
    help="Directory-reader service account email. Defaults to $WIF_SA_EMAIL.",
    default=lambda: os.environ.get("WIF_SA_EMAIL"),
)
@click.option(
    "--admin-subject",
    help="Workspace admin to impersonate. Defaults to $WIF_ADMIN_SUBJECT.",
    default=lambda: os.environ.get("WIF_ADMIN_SUBJECT"),
)
@click.option(
    "--dry-run",
    help="Report what would be revoked without revoking anything.",
    is_flag=True,
    default=False,
    show_default=True,
)
@click.pass_context
def cmd_sync_google_users(ctx: click.Context, **kwargs):
    """
    Revoke certificates of users deactivated in Google Workspace.

    Reconciles the certificate index against the directory: every valid
    user certificate whose owner is suspended, deleted or otherwise absent is
    revoked. The server's own certificate is never a candidate.

    CONFIGURATION comes from three environment variables, which on a
    module-provisioned instance are written by Terraform to
    /opt/openvpn-wif/wif.env (the file holds no secret -- the credential it
    points at is a keyless federation config, not a key):

    \b
      GOOGLE_APPLICATION_CREDENTIALS  path to the WIF credential config
      WIF_SA_EMAIL                    directory-reader service account
      WIF_ADMIN_SUBJECT               Workspace admin to impersonate

    So a by-hand run on an instance is source-then-invoke. --dry-run first is
    the safe habit: it prints exactly who would be revoked and touches nothing.
    Revoking is the default (the scheduled job invokes the command bare); there
    is no separate "enforce" flag to remember.

    \b
      # load the config Terraform wrote
      . /opt/openvpn-wif/wif.env
      # preview -- lists deactivated users, revokes nothing
      ih-openvpn sync-google-users --dry-run
      # apply
      ih-openvpn sync-google-users
      # confirm -- the revoked cert now shows state R
      ih-openvpn list-clients

    Exit status is a contract with the Puppet cron wrapper: 0 on success, 78
    when the Google side is not usable yet (most often domain-wide delegation
    not authorized), any other code on a genuine failure. Point --config-dir at
    a different OpenVPN installation, or override the service account / admin
    subject, with the options below.
    """
    config_dir = ctx.obj["config_dir"]
    service_account = kwargs["service_account"]
    admin_subject = kwargs["admin_subject"]
    dry_run = kwargs["dry_run"]

    # Absent configuration is the pre-deployment state, not a usage error, so it
    # exits EX_CONFIG rather than click's UsageError.
    for name, value in (
        ("--service-account/$WIF_SA_EMAIL", service_account),
        ("--admin-subject/$WIF_ADMIN_SUBJECT", admin_subject),
    ):
        if not value:
            LOG.info("%s is not set; the Google integration is not configured yet.", name)
            sys.exit(EX_CONFIG)

    certificate_index = index_path(config_dir)
    try:
        certificates = valid_user_certificates(certificate_index)
    except FileNotFoundError:
        LOG.info("%s does not exist; the PKI is not initialized yet.", certificate_index)
        sys.exit(EX_CONFIG)

    try:
        active_users = get_active_directory_users(service_account, admin_subject)
    except GoogleNotConfigured as err:
        LOG.info("Google Workspace is not configured yet: %s", err)
        sys.exit(EX_CONFIG)
    except ImportError as err:
        LOG.info("google libraries are not installed yet: %s", err)
        sys.exit(EX_CONFIG)

    # An empty directory response would make every certificate look orphaned.
    # Treat it as a failed lookup rather than as "everyone was deactivated".
    if not active_users:
        LOG.error("The directory returned no active users; refusing to revoke every certificate.")
        sys.exit(1)

    stale = sorted(certificate for certificate in certificates if certificate.lower() not in active_users)
    if not stale:
        LOG.info(
            "Checked %d certificate(s) against %d active user(s); nothing to revoke.",
            len(certificates),
            len(active_users),
        )
        return

    if dry_run:
        # Deliberately before any easy-rsa call, so --dry-run cannot touch the
        # PKI no matter what happens below.
        LOG.info(
            "DRY RUN: would revoke %d certificate(s) of deactivated user(s): %s",
            len(stale),
            ", ".join(stale),
        )
        LOG.info("DRY RUN: nothing was revoked; re-run without --dry-run to apply.")
        return

    LOG.info("Revoking %d certificate(s) of deactivated user(s): %s", len(stale), ", ".join(stale))
    failed = []
    for common_name in stale:
        try:
            revoke_client(ctx.obj["easyrsa_path"], common_name, config_dir)
            LOG.info("VPN access for client %s is revoked.", common_name)
        except CalledProcessError as err:
            # Keep going: one certificate easy-rsa cannot revoke should not
            # leave the remaining deactivated users with working access.
            LOG.error("Failed to revoke %s: %s", common_name, err)
            failed.append(common_name)

    if failed:
        LOG.error("Failed to revoke %d certificate(s): %s", len(failed), ", ".join(failed))
        sys.exit(1)
