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
    proc = None
    try:
        proc = run(cmd, capture_output=True, check=True)
        sys.exit(proc.returncode)

    except FileNotFoundError as err:
        LOG.exception(err)
        comment = f"Command `{' '.join(cmd)}` failed to start.\n"
        comment += f"Stack trace:\n```\n{traceback.format_exc()}\n```\n"
        sys.exit(1)

    except CalledProcessError as err:
        LOG.exception(err)
        sys.exit(1)

    finally:
        if proc:
            sys.stdout.write(proc.stdout.decode())
            sys.stderr.write(proc.stderr.decode())
            comment = f"Command `{' '.join(cmd)}` exited with code {proc.returncode}.\n"
            comment += f"**Standard output**:\n```\n{proc.stdout.decode() or 'No output'}\n```\n"
            comment += f"**Standard error**:\n```\n{proc.stderr.decode() or 'No output'}\n```\n"
            pull_request.publish_comment(comment)
            sys.exit(proc.returncode)
