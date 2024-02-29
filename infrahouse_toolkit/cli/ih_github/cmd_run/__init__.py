"""
.. topic:: ``ih-github run``

    A ``ih-github run`` subcommand.

    See ``ih-github run --help`` for more details.
"""
import logging
import sys
import traceback
from subprocess import CalledProcessError, run

import click

from infrahouse_toolkit.terraform.githubpr import GitHubPR

LOG = logging.getLogger()


@click.command(
    name="run",
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
@click.option("--github-token", help="Personal access token for GitHub.", envvar="GITHUB_TOKEN")
@click.argument("repo")
@click.argument("pull_request_number", type=click.INT)
@click.pass_context
def cmd_run(ctx, *args, **kwargs):
    """
    Run a command and publish its output to as a comment in GitHub pull request.

    For instance
    """
    LOG.debug("args = %s", args)
    LOG.debug("kwargs = %s", kwargs)
    LOG.debug(ctx.args)
    cmd = ctx.args
    comment = None
    pull_request = GitHubPR(kwargs["repo"], kwargs["pull_request_number"], github_token=kwargs["github_token"])

    try:
        proc = run(cmd, capture_output=True, check=True)
        comment = f"""
Command `{" ".join(cmd)}` exited with code {proc.returncode}.

**Standard output**:
```
{proc.stdout.decode() or "No output"}
```
**Standard error**:
```
{proc.stderr.decode() or "No output"}
```
"""
        sys.stdout.write(proc.stdout.decode())
        sys.stderr.write(proc.stderr.decode())

    except (CalledProcessError, FileNotFoundError) as err:
        LOG.exception(err)
        comment = f"""
Command `{" ".join(cmd)}` failed to start.

Stack trace:
```
{traceback.format_exc()}
```
"""

    finally:
        pull_request.publish_comment(comment)
