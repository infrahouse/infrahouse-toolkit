"""
.. topic:: ``ih-github scan``

    A ``ih-github scan`` subcommand.

    See ``ih-github scan --help`` for more details.
"""

import json
import logging
import sys
from datetime import datetime, timedelta
from subprocess import PIPE, Popen

import click

from infrahouse_toolkit.cli.utils import check_dependencies
from infrahouse_toolkit.terraform.githubpr import GitHubPR

LOG = logging.getLogger()
DEPENDENCIES = ["osv-scanner"]


@click.command(
    name="scan",
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
@click.option("--github-token", help="Personal access token for GitHub.", envvar="GITHUB_TOKEN")
@click.option("--repo", help="GitHub repository name in a long format e.g. infrahouse/infrahouse-toolkit.")
@click.option("--pull-request", help="GitHub pull request number.", type=click.INT)
@click.option("--sla-critical", help="SLA in days on when critical vulnerabilities should be fixed.", default=15)
@click.option("--sla-high", help="SLA in days on when high vulnerabilities should be fixed.", default=30)
@click.option("--sla-medium", help="SLA in days on when medium vulnerabilities should be fixed.", default=45)
@click.option("--sla-low", help="SLA in days on when medium vulnerabilities should be fixed.", default=90)
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
    # pull_request = GitHubPR(kwargs["repo"], kwargs["pull_request_number"], github_token=kwargs["github_token"])
    cmd = ["osv-scanner", "scan", "--format", "markdown", "--recursive", "--verbosity", "warn", "./"]
    cmd.extend(cmd_args)
    sla_map = {
        "CRITICAL": kwargs["sla_critical"],
        "HIGH": kwargs["sla_high"],
        "MODERATE": kwargs["sla_medium"],
        "MEDIUM": kwargs["sla_medium"],
        "LOW": kwargs["sla_low"],
    }
    comment = None
    try:
        with Popen(cmd, stderr=PIPE, stdout=PIPE) as proc:
            LOG.info("Launched command: %s", " ".join(cmd))
            vuln_table, cerr = proc.communicate()
            return_code = proc.returncode
            if cerr:
                LOG.error(cerr)
            if return_code != 0:
                comment = "# Vulnerabilities report\n"
                comment += vuln_table.decode()
                for vuln in _get_vulnerability_details(cmd_args):
                    future_date = datetime.now() + timedelta(days=sla_map.get(vuln["severity"], 30))
                    comment += f"""
## {vuln["name"]}=={vuln["version"]}
The package `{vuln["name"]}` (version {vuln["version"]}) has a {vuln["severity"]}-severity vulnerability.

If you can upgrade to non-vulnerable version, please do.
If you can't upgrade now, you can append this entry to `osv-scanner.toml`

```
[[IgnoredVulns]]
id = "{vuln["id"]}"
ignoreUntil = {future_date.strftime("%Y-%m-%d")} # Optional exception expiry date
reason = "Detailed explanation why the vulnerability is ignored and how it is planned to be fixed."
```
"""
            sys.stdout.write(vuln_table.decode())

    finally:
        if comment:
            print(comment)
            if kwargs["repo"] and kwargs["pull_request"]:
                pull_request = GitHubPR(kwargs["repo"], kwargs["pull_request"], github_token=kwargs["github_token"])
                pull_request.publish_comment(comment)

    sys.exit(return_code)


def _get_vulnerability_details(extra_args):
    """
    returns a JSON
    [
        {
            name: "pymysql"
            version: "1.2.3"
            id: "GHSA-7wqh-767x-r66v"
            severity: "MODERATE"
        }
    ]
    """
    cmd = ["osv-scanner", "scan", "--format", "json", "--recursive", "--verbosity", "warn", "./"]
    cmd.extend(extra_args)
    return_value = []
    with Popen(cmd, stderr=PIPE, stdout=PIPE) as proc:
        LOG.debug("Launched command: %s", " ".join(cmd))
        cout, cerr = proc.communicate()
        if cerr:
            LOG.error(cerr)
        response = json.loads(cout)
        for result in response["results"]:
            for package_item in result["packages"]:
                for vuln in package_item["vulnerabilities"]:
                    return_value.append(
                        {
                            "name": package_item["package"]["name"],
                            "version": package_item["package"]["version"],
                            "id": vuln["id"],
                            "severity": vuln["database_specific"]["severity"],
                        }
                    )
        return return_value
