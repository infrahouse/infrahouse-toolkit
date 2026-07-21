"""
Unit tests for :py:mod:`infrahouse_toolkit.cli.ih_openvpn.cmd_sync_google_users`.

The exit-status contract is the point of this file. The Puppet wrapper that runs
the command on a cron treats 78 (EX_CONFIG) as "not configured yet" -- it logs
and exits 0 -- and anything else non-zero as a real failure worth mailing an
operator about. If a not-yet-configured condition were to leak out as exit 1,
every OpenVPN node in the fleet would mail root daily until someone finished the
Google setup. These tests pin that boundary.
"""

import importlib
from subprocess import CalledProcessError
from unittest import mock

import pytest
from click.testing import CliRunner

from infrahouse_toolkit.cli.ih_openvpn.cmd_sync_google_users import (
    EX_CONFIG,
    GoogleNotConfigured,
    cmd_sync_google_users,
    get_active_directory_users,
)

# The package and the Click command share the name cmd_sync_google_users, so
# ih_openvpn.cmd_sync_google_users resolves to the command, not the module --
# which makes a dotted-string mock target (or `import ... as`) land on the
# command on some import orders (passed 3.11-3.14, failed 3.10). import_module
# returns the real module object from sys.modules, so patch.object is stable.
sync_module = importlib.import_module("infrahouse_toolkit.cli.ih_openvpn.cmd_sync_google_users")

SERVER_DN = "/C=US/O=InfraHouse Inc./CN=server"


@pytest.fixture(name="config_dir")
def _config_dir(tmp_path):
    """An OpenVPN config directory with a PKI holding a server and two user certificates."""
    pki = tmp_path / "pki"
    pki.mkdir()
    (pki / "index.txt").write_text(
        f"V\t300101000000Z\t\t01\tunknown\t{SERVER_DN}\n"
        "V\t300101000000Z\t\t02\tunknown\t/CN=alice@infrahouse.com\n"
        "V\t300101000000Z\t\t03\tunknown\t/CN=bob@infrahouse.com\n",
        encoding="utf-8",
    )
    return str(tmp_path)


def run(config_dir, extra_args=None, **kwargs):
    """Invoke the command with the context the ih-openvpn group would normally supply."""
    return CliRunner().invoke(
        cmd_sync_google_users,
        [
            "--service-account",
            "sa@example.iam.gserviceaccount.com",
            "--admin-subject",
            "admin@infrahouse.com",
        ]
        + (extra_args or []),
        obj={"easyrsa_path": "/usr/share/easy-rsa/easyrsa", "config_dir": config_dir},
        **kwargs,
    )


def test_dry_run_revokes_nothing(config_dir):
    """
    --dry-run reports the same set but never touches the PKI.

    bob is absent from the directory, so without the flag this exact invocation
    revokes bob's certificate (see test_revokes_only_deactivated_users).
    """
    with mock.patch.object(sync_module, "get_active_directory_users", return_value={"alice@infrahouse.com"}):
        with mock.patch.object(sync_module, "revoke_client") as revoke:
            result = run(config_dir, ["--dry-run"])
    assert result.exit_code == 0
    revoke.assert_not_called()


def test_revoking_is_the_default(config_dir):
    """
    Omitting --dry-run revokes.

    Pins the default the scheduled job depends on: the Puppet wrapper invokes
    the command bare, and must not silently become a no-op.
    """
    with mock.patch.object(sync_module, "get_active_directory_users", return_value={"alice@infrahouse.com"}):
        with mock.patch.object(sync_module, "revoke_client") as revoke:
            result = run(config_dir)
    assert result.exit_code == 0
    revoke.assert_called_once()


def test_exits_ex_config_when_delegation_not_authorized(config_dir):
    """
    Unauthorized domain-wide delegation must exit 78, not 1.

    This is the case the operator hits between deploying the Terraform and
    authorizing the client id in the Workspace admin console.
    """
    with mock.patch.object(
        sync_module, "get_active_directory_users", side_effect=GoogleNotConfigured("not authorized")
    ):
        result = run(config_dir)
    assert result.exit_code == EX_CONFIG


def test_exits_ex_config_when_credentials_unusable(config_dir):
    """
    Unresolvable Application Default Credentials must exit 78, not 1.

    Hit when the Terraform-written credential config is missing or malformed, or
    when IMDS cannot be reached to source the AWS identity. Regression test: this
    previously escaped as an uncaught DefaultCredentialsError traceback, which
    the wrapper would have reported as a real failure and mailed daily.
    """
    with mock.patch.object(
        sync_module,
        "get_active_directory_users",
        side_effect=GoogleNotConfigured("no usable application default credentials"),
    ):
        result = run(config_dir)
    assert result.exit_code == EX_CONFIG


def test_default_credentials_error_becomes_not_configured():
    """
    The real google-auth exception type is translated, not just its message.

    Exercises get_active_directory_users directly with google.auth.default
    patched, so the translation is pinned against the actual library error
    rather than a stand-in the test itself invented.
    """
    google_auth = pytest.importorskip("google.auth")
    from google.auth.exceptions import (  # pylint: disable=import-outside-toplevel
        DefaultCredentialsError,
    )

    with mock.patch.object(google_auth, "default", side_effect=DefaultCredentialsError("bad config")):
        with pytest.raises(GoogleNotConfigured):
            get_active_directory_users("sa@example.iam.gserviceaccount.com", "admin@infrahouse.com")


def test_exits_ex_config_without_service_account(config_dir):
    """Missing configuration is the pre-deployment state, not a usage error."""
    result = CliRunner().invoke(
        cmd_sync_google_users,
        ["--admin-subject", "admin@infrahouse.com"],
        obj={"easyrsa_path": "/usr/share/easy-rsa/easyrsa", "config_dir": config_dir},
    )
    assert result.exit_code == EX_CONFIG


def test_exits_ex_config_when_pki_absent(tmp_path):
    """An instance whose PKI has not been generated yet is not ready."""
    with mock.patch.object(sync_module, "get_active_directory_users", return_value={"alice@infrahouse.com"}):
        result = run(str(tmp_path))
    assert result.exit_code == EX_CONFIG


def test_revokes_only_deactivated_users(config_dir):
    """bob is absent from the directory, so only bob's certificate is revoked."""
    with mock.patch.object(sync_module, "get_active_directory_users", return_value={"alice@infrahouse.com"}):
        with mock.patch.object(sync_module, "revoke_client") as revoke:
            result = run(config_dir)
    assert result.exit_code == 0
    revoke.assert_called_once_with("/usr/share/easy-rsa/easyrsa", "bob@infrahouse.com", config_dir)


def test_never_revokes_the_server_certificate(config_dir):
    """
    Even when the directory knows nobody, the server certificate is untouchable.

    An empty active-user set is refused outright, and CN=server would be filtered
    out regardless -- two independent guards against killing the VPN.
    """
    with mock.patch.object(sync_module, "get_active_directory_users", return_value=set()):
        with mock.patch.object(sync_module, "revoke_client") as revoke:
            result = run(config_dir)
    assert result.exit_code == 1
    revoke.assert_not_called()


def test_nothing_to_do_when_all_users_active(config_dir):
    """A fully reconciled fleet revokes nothing and succeeds."""
    with mock.patch.object(
        sync_module,
        "get_active_directory_users",
        return_value={"alice@infrahouse.com", "bob@infrahouse.com"},
    ):
        with mock.patch.object(sync_module, "revoke_client") as revoke:
            result = run(config_dir)
    assert result.exit_code == 0
    revoke.assert_not_called()


def test_case_insensitive_match(config_dir):
    """Directory addresses differing only in case are still the same user."""
    with mock.patch.object(
        sync_module,
        "get_active_directory_users",
        return_value={"alice@infrahouse.com", "BOB@infrahouse.com".lower()},
    ):
        with mock.patch.object(sync_module, "revoke_client") as revoke:
            result = run(config_dir)
    assert result.exit_code == 0
    revoke.assert_not_called()


def test_continues_after_a_failed_revocation(config_dir):
    """One un-revokable certificate must not leave the others with working access."""
    with mock.patch.object(sync_module, "get_active_directory_users", return_value=set(["carol@infrahouse.com"])):
        with mock.patch.object(sync_module, "revoke_client", side_effect=CalledProcessError(1, "easyrsa")) as revoke:
            result = run(config_dir)
    # Both alice and bob are stale here; both were attempted despite the failure.
    assert revoke.call_count == 2
    assert result.exit_code == 1
