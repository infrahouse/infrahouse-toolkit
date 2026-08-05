"""
.. topic:: ``ih-github scan``

    A ``ih-github scan`` subcommand.

    See ``ih-github scan --help`` for more details.
"""

import logging
import sys
from datetime import datetime, timedelta
from os import path as osp
from subprocess import PIPE, Popen

import click

from infrahouse_toolkit.cli.utils import check_dependencies
from infrahouse_toolkit.osv import (
    SEVERITY_CRITICAL,
    SEVERITY_HIGH,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    SEVERITY_MODERATE,
)
from infrahouse_toolkit.osv.scan_report import ScanReport
from infrahouse_toolkit.terraform.githubpr import GitHubPR

LOG = logging.getLogger()
DEPENDENCIES = ["osv-scanner"]
DEFAULT_SLA_DAYS = 30


@click.command(
    name="scan",
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
@click.option("--github-token", help="Personal access token for GitHub.", envvar="GITHUB_TOKEN")
@click.option(
    "--osv-config", help="Path to osv-scanner configuration file.", default="osv-scanner.toml", show_default=True
)
@click.option("--repo", help="GitHub repository name in a long format e.g. infrahouse/infrahouse-toolkit.")
@click.option("--pull-request", help="GitHub pull request number.", type=click.INT)
@click.option(
    "--sla-critical",
    help="SLA in days on when critical vulnerabilities should be fixed.",
    default=15,
    show_default=True,
)
@click.option(
    "--sla-high", help="SLA in days on when high vulnerabilities should be fixed.", default=30, show_default=True
)
@click.option(
    "--sla-medium", help="SLA in days on when medium vulnerabilities should be fixed.", default=45, show_default=True
)
@click.option(
    "--sla-low", help="SLA in days on when medium vulnerabilities should be fixed.", default=90, show_default=True
)
@click.pass_context
def cmd_scan(ctx, *args, **kwargs):
    """
    Scan the current directory for dependency vulnerabilities.
    If found, publish a report as a pull request comment.
    """
    LOG.debug("args = %s", args)
    LOG.debug("kwargs = %s", kwargs)
    cmd_args = ctx.args
    LOG.debug("cmd_args = %s", cmd_args)
    check_dependencies(DEPENDENCIES)
    osv_config = kwargs["osv_config"]
    cmd = ["osv-scanner", "scan", "--format", "markdown", "--recursive", "--verbosity", "warn"]
    if osp.exists(osv_config):
        cmd.extend(["--config", osv_config])
    cmd.extend(cmd_args)
    cmd.extend(["./"])
    sla_map = {
        SEVERITY_CRITICAL: kwargs["sla_critical"],
        SEVERITY_HIGH: kwargs["sla_high"],
        SEVERITY_MODERATE: kwargs["sla_medium"],
        SEVERITY_MEDIUM: kwargs["sla_medium"],
        SEVERITY_LOW: kwargs["sla_low"],
    }
    comment = None
    try:
        with Popen(cmd, stderr=PIPE, stdout=PIPE) as proc:
            LOG.info("Launched command: %s", " ".join(cmd))
            vuln_table, cerr = proc.communicate()
            return_code = proc.returncode

            if cerr:
                LOG.error(cerr.decode())

            if return_code == 1:
                comment = "# Vulnerabilities report\n"
                comment += vuln_table.decode()
                for vuln in ScanReport(config_file=osv_config, extra_args=cmd_args).vulnerabilities:
                    future_date = datetime.now() + timedelta(days=sla_map.get(vuln.severity, DEFAULT_SLA_DAYS))
                    comment += f"""
## {vuln.package}
The package `{vuln.package.name}` (version {vuln.package.version}) has a {vuln.severity}-severity vulnerability.

If you're able to upgrade to a non-vulnerable version, we recommend doing so.
If upgrading isn't currently possible, consider adding this entry to your `{osv_config}` file
in the root directory of this repository.

```
[[IgnoredVulns]]
id = "{vuln.id}"
ignoreUntil = {future_date.strftime("%Y-%m-%d")} # Optional exception expiry date
reason = "Detailed explanation why the vulnerability is ignored and how it is planned to be fixed."
```
"""
            elif return_code == 128:
                LOG.warning("No package lock file found, will assume no vulnerabilities.")
                sys.exit(0)
            else:
                LOG.warning("osv-scanner exited with unknown exit code %d", return_code)

            sys.stdout.write(vuln_table.decode())

    finally:
        if comment:
            print(comment)
            if kwargs["repo"] and kwargs["pull_request"]:
                pull_request = GitHubPR(kwargs["repo"], kwargs["pull_request"], github_token=kwargs["github_token"])
                pull_request.publish_comment(comment)

    sys.exit(return_code)
