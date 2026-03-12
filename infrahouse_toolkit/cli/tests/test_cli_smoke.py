"""
Smoke tests for all CLI commands.

These tests invoke ``--help`` (and ``--version`` where available) on every CLI
entry point and subcommand.  They catch import errors, Click wiring bugs, and
dependency breakage (e.g. upstream signature changes) without requiring AWS
credentials or any external services.

Several Click groups run validation in their callback (create AWS sessions,
check passwords, verify external binaries) before the subcommand is reached.
For those groups we supply the minimum arguments needed to satisfy the callback
so that ``--help`` can be displayed.  Groups that require external binaries not
available in CI (easyrsa, skeema, reprepro) are skipped when the binary is
missing.

See https://github.com/infrahouse/infrahouse-toolkit/issues/206
"""

import shutil
from typing import List, Tuple

import pytest
from click.testing import CliRunner

from infrahouse_toolkit import __version__
from infrahouse_toolkit.cli.ih_aws import ih_aws
from infrahouse_toolkit.cli.ih_certbot import ih_certbot
from infrahouse_toolkit.cli.ih_ec2 import ih_ec2
from infrahouse_toolkit.cli.ih_elastic import ih_elastic
from infrahouse_toolkit.cli.ih_github import ih_github
from infrahouse_toolkit.cli.ih_mysql import ih_mysql
from infrahouse_toolkit.cli.ih_openvpn import ih_openvpn
from infrahouse_toolkit.cli.ih_plan import ih_plan
from infrahouse_toolkit.cli.ih_puppet import ih_puppet
from infrahouse_toolkit.cli.ih_registry import ih_registry
from infrahouse_toolkit.cli.ih_s3 import ih_s3
from infrahouse_toolkit.cli.ih_s3_reprepro import ih_s3_reprepro
from infrahouse_toolkit.cli.ih_secrets import ih_secrets
from infrahouse_toolkit.cli.ih_skeema import ih_skeema

# ---------------------------------------------------------------------------
# External-binary availability (for groups whose callback shells out)
# ---------------------------------------------------------------------------
_has_easyrsa = shutil.which("easyrsa") is not None or shutil.which("/usr/share/easy-rsa/easyrsa") is not None
_has_skeema = shutil.which("skeema") is not None
_has_reprepro_deps = all(shutil.which(b) is not None for b in ("reprepro", "gpg", "s3fs"))


# ---------------------------------------------------------------------------
# --help smoke tests
# ---------------------------------------------------------------------------
# Each tuple is (cli_entry_point, args_for_invoke).
#
# * Groups whose callback needs AWS region get ``--aws-region us-east-1``.
# * ih-elastic needs ``--password dummy`` to skip secret look-up.
# * ih-s3-reprepro needs ``--bucket dummy`` and external binaries.
# * ih-openvpn / ih-skeema need their respective binaries.
#
# The top-level ``--help`` on each group is always safe because Click
# short-circuits before invoking the group callback.
# ---------------------------------------------------------------------------
HELP_CASES: List[Tuple] = [
    # ── ih-aws (group callback creates AWS session → needs --aws-region) ──
    (ih_aws, ["--help"]),
    (ih_aws, ["--aws-region", "us-east-1", "autoscaling", "--help"]),
    (ih_aws, ["--aws-region", "us-east-1", "autoscaling", "mark-unhealthy", "--help"]),
    (ih_aws, ["--aws-region", "us-east-1", "autoscaling", "complete", "--help"]),
    (ih_aws, ["--aws-region", "us-east-1", "autoscaling", "scale-in", "--help"]),
    (ih_aws, ["--aws-region", "us-east-1", "credentials", "--help"]),
    (ih_aws, ["--aws-region", "us-east-1", "ecs", "--help"]),
    (ih_aws, ["--aws-region", "us-east-1", "ecs", "wait-services-stable", "--help"]),
    (ih_aws, ["--aws-region", "us-east-1", "resources", "--help"]),
    (ih_aws, ["--aws-region", "us-east-1", "resources", "list", "--help"]),
    (ih_aws, ["--aws-region", "us-east-1", "resources", "delete", "--help"]),
    # ── ih-certbot (single command, no group callback) ────────────────────
    (ih_certbot, ["--help"]),
    # ── ih-ec2 (group callback creates EC2 client → needs --aws-region) ───
    (ih_ec2, ["--help"]),
    (ih_ec2, ["--aws-region", "us-east-1", "launch", "--help"]),
    (ih_ec2, ["--aws-region", "us-east-1", "list", "--help"]),
    (ih_ec2, ["--aws-region", "us-east-1", "instance-types", "--help"]),
    (ih_ec2, ["--aws-region", "us-east-1", "terminate", "--help"]),
    (ih_ec2, ["--aws-region", "us-east-1", "subnets", "--help"]),
    (ih_ec2, ["--aws-region", "us-east-1", "launch-templates", "--help"]),
    (ih_ec2, ["--aws-region", "us-east-1", "tags", "--help"]),
    # ── ih-elastic (group callback validates password) ────────────────────
    (ih_elastic, ["--help"]),
    (ih_elastic, ["--password", "dummy", "api", "--help"]),
    (ih_elastic, ["--password", "dummy", "cat", "--help"]),
    (ih_elastic, ["--password", "dummy", "cat", "repositories", "--help"]),
    (ih_elastic, ["--password", "dummy", "cat", "snapshots", "--help"]),
    (ih_elastic, ["--password", "dummy", "cat", "shards", "--help"]),
    (ih_elastic, ["--password", "dummy", "cat", "nodes", "--help"]),
    (ih_elastic, ["--password", "dummy", "cluster", "--help"]),
    (ih_elastic, ["--password", "dummy", "cluster", "allocation-explain", "--help"]),
    (ih_elastic, ["--password", "dummy", "cluster", "decommission-node", "--help"]),
    (ih_elastic, ["--password", "dummy", "cluster", "commission-node", "--help"]),
    (ih_elastic, ["--password", "dummy", "cluster-health", "--help"]),
    (ih_elastic, ["--password", "dummy", "passwd", "--help"]),
    (ih_elastic, ["--password", "dummy", "security", "--help"]),
    (ih_elastic, ["--password", "dummy", "security", "api-key", "--help"]),
    (ih_elastic, ["--password", "dummy", "security", "api-key", "list", "--help"]),
    (ih_elastic, ["--password", "dummy", "security", "api-key", "create", "--help"]),
    (ih_elastic, ["--password", "dummy", "security", "api-key", "delete", "--help"]),
    (ih_elastic, ["--password", "dummy", "snapshots", "--help"]),
    (ih_elastic, ["--password", "dummy", "snapshots", "status", "--help"]),
    (ih_elastic, ["--password", "dummy", "snapshots", "create-repository", "--help"]),
    (ih_elastic, ["--password", "dummy", "snapshots", "delete-repository", "--help"]),
    (ih_elastic, ["--password", "dummy", "snapshots", "create", "--help"]),
    (ih_elastic, ["--password", "dummy", "snapshots", "restore", "--help"]),
    (ih_elastic, ["--password", "dummy", "snapshots", "policy", "--help"]),
    # ── ih-github (group callback is safe) ────────────────────────────────
    (ih_github, ["--help"]),
    (ih_github, ["run", "--help"]),
    (ih_github, ["runner", "--help"]),
    (ih_github, ["runner", "list", "--help"]),
    (ih_github, ["runner", "register", "--help"]),
    (ih_github, ["runner", "deregister", "--help"]),
    (ih_github, ["runner", "is-registered", "--help"]),
    (ih_github, ["runner", "download", "--help"]),
    (ih_github, ["runner", "check-health", "--help"]),
    (ih_github, ["backup", "--help"]),
    (ih_github, ["scan", "--help"]),
    # ── ih-mysql (group callback is safe) ─────────────────────────────────
    (ih_mysql, ["--help"]),
    (ih_mysql, ["bootstrap", "--help"]),
    # ── ih-openvpn (group callback shells out to easyrsa) ─────────────────
    (ih_openvpn, ["--help"]),
    pytest.param(
        ih_openvpn,
        ["list-clients", "--help"],
        marks=pytest.mark.skipif(not _has_easyrsa, reason="easyrsa not installed"),
    ),
    pytest.param(
        ih_openvpn,
        ["revoke-client", "--help"],
        marks=pytest.mark.skipif(not _has_easyrsa, reason="easyrsa not installed"),
    ),
    # ── ih-plan (group callback is safe) ──────────────────────────────────
    (ih_plan, ["--help"]),
    (ih_plan, ["upload", "--help"]),
    (ih_plan, ["download", "--help"]),
    (ih_plan, ["remove", "--help"]),
    (ih_plan, ["publish", "--help"]),
    (ih_plan, ["min-permissions", "--help"]),
    # ── ih-puppet (group callback is safe) ────────────────────────────────
    (ih_puppet, ["--help"]),
    (ih_puppet, ["apply", "--help"]),
    # ── ih-registry (group callback is safe) ──────────────────────────────
    (ih_registry, ["--help"]),
    (ih_registry, ["upload", "--help"]),
    # ── ih-s3 (group callback creates S3 client → needs --aws-region) ─────
    (ih_s3, ["--help"]),
    (ih_s3, ["--aws-region", "us-east-1", "upload-logs", "--help"]),
    # ── ih-s3-reprepro (needs --bucket + external deps) ───────────────────
    (ih_s3_reprepro, ["--help"]),
    pytest.param(
        ih_s3_reprepro,
        ["--bucket", "dummy", "list", "--help"],
        marks=pytest.mark.skipif(not _has_reprepro_deps, reason="reprepro/gpg/s3fs not installed"),
    ),
    pytest.param(
        ih_s3_reprepro,
        ["--bucket", "dummy", "checkpool", "--help"],
        marks=pytest.mark.skipif(not _has_reprepro_deps, reason="reprepro/gpg/s3fs not installed"),
    ),
    pytest.param(
        ih_s3_reprepro,
        ["--bucket", "dummy", "check", "--help"],
        marks=pytest.mark.skipif(not _has_reprepro_deps, reason="reprepro/gpg/s3fs not installed"),
    ),
    pytest.param(
        ih_s3_reprepro,
        ["--bucket", "dummy", "remove", "--help"],
        marks=pytest.mark.skipif(not _has_reprepro_deps, reason="reprepro/gpg/s3fs not installed"),
    ),
    pytest.param(
        ih_s3_reprepro,
        ["--bucket", "dummy", "includedeb", "--help"],
        marks=pytest.mark.skipif(not _has_reprepro_deps, reason="reprepro/gpg/s3fs not installed"),
    ),
    pytest.param(
        ih_s3_reprepro,
        ["--bucket", "dummy", "dumpunreferenced", "--help"],
        marks=pytest.mark.skipif(not _has_reprepro_deps, reason="reprepro/gpg/s3fs not installed"),
    ),
    pytest.param(
        ih_s3_reprepro,
        ["--bucket", "dummy", "deleteunreferenced", "--help"],
        marks=pytest.mark.skipif(not _has_reprepro_deps, reason="reprepro/gpg/s3fs not installed"),
    ),
    pytest.param(
        ih_s3_reprepro,
        ["--bucket", "dummy", "set-secret-value", "--help"],
        marks=pytest.mark.skipif(not _has_reprepro_deps, reason="reprepro/gpg/s3fs not installed"),
    ),
    pytest.param(
        ih_s3_reprepro,
        ["--bucket", "dummy", "get-secret-value", "--help"],
        marks=pytest.mark.skipif(not _has_reprepro_deps, reason="reprepro/gpg/s3fs not installed"),
    ),
    pytest.param(
        ih_s3_reprepro,
        ["--bucket", "dummy", "migrate", "--help"],
        marks=pytest.mark.skipif(not _has_reprepro_deps, reason="reprepro/gpg/s3fs not installed"),
    ),
    # ── ih-secrets (group callback creates SM client → needs --aws-region) ─
    (ih_secrets, ["--help"]),
    (ih_secrets, ["--aws-region", "us-east-1", "list", "--help"]),
    (ih_secrets, ["--aws-region", "us-east-1", "get", "--help"]),
    (ih_secrets, ["--aws-region", "us-east-1", "set", "--help"]),
    # ── ih-skeema (group callback shells out to skeema) ───────────────────
    (ih_skeema, ["--help"]),
    pytest.param(
        ih_skeema, ["run", "--help"], marks=pytest.mark.skipif(not _has_skeema, reason="skeema not installed")
    ),
]


def _test_id(val) -> str:
    """Generate a human-readable pytest ID for each parametrized case."""
    # pytest.param wraps the values; unwrap if needed.
    if hasattr(val, "values"):
        cli_func, args = val.values
    else:
        cli_func, args = val
    name = cli_func.name if hasattr(cli_func, "name") else cli_func.__name__
    # Show only the structurally interesting parts (drop --aws-region/--password/--bucket filler).
    visible = [a for a in args if not a.startswith("--aws-region") and a not in ("us-east-1", "dummy")]
    if "--password" in args:
        visible = [a for a in visible if a != "--password"]
    if "--bucket" in args:
        visible = [a for a in visible if a != "--bucket"]
    return f"{name} {' '.join(visible)}"


@pytest.mark.parametrize("cli_func,args", HELP_CASES, ids=[_test_id(c) for c in HELP_CASES])
def test_help(cli_func, args: List[str]) -> None:
    """Every CLI command must respond to ``--help`` with exit code 0."""
    runner = CliRunner()
    # noinspection PyTypeChecker
    result = runner.invoke(cli_func, args)
    assert result.exit_code == 0, f"'--help' failed for {cli_func.name} {' '.join(args)}:\n{result.output}"


# ---------------------------------------------------------------------------
# --version smoke tests
# ---------------------------------------------------------------------------
# Only tools that declare @click.version_option() are listed here.
# ih-certbot, ih-openvpn, ih-s3-reprepro, ih-skeema currently lack it.
# ---------------------------------------------------------------------------
VERSION_CASES = [
    ih_aws,
    ih_ec2,
    ih_elastic,
    ih_github,
    ih_mysql,
    ih_plan,
    ih_puppet,
    ih_registry,
    ih_s3,
    ih_secrets,
]


@pytest.mark.parametrize(
    "cli_func",
    VERSION_CASES,
    ids=[c.name if hasattr(c, "name") else c.__name__ for c in VERSION_CASES],
)
def test_version(cli_func) -> None:
    """Every CLI tool with ``--version`` must print the package version."""
    runner = CliRunner()
    # noinspection PyTypeChecker
    result = runner.invoke(cli_func, ["--version"])
    assert result.exit_code == 0, f"'--version' failed for {cli_func.name}:\n{result.output}"
    assert __version__ in result.output, f"Expected version {__version__} in output:\n{result.output}"
