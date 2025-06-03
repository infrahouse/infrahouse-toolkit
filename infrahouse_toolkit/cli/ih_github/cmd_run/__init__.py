"""
.. topic:: ``ih-github run``

    A ``ih-github run`` subcommand.

    See ``ih-github run --help`` for more details.
"""

import logging
import sys
import time
import traceback
from subprocess import PIPE, Popen

import click

from infrahouse_toolkit.terraform.githubpr import GitHubPR

LOG = logging.getLogger()


@click.command(
    name="run",
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
@click.option("--github-token", help="Personal access token for GitHub.", envvar="GITHUB_TOKEN")
@click.option("--run-timeout", help="How many seconds the command it allowed to run", show_default=True, default=3600)
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
    comment_salt = f"Command `{' '.join(cmd)}`"
    try:
        with Popen(cmd, stderr=PIPE, stdout=PIPE) as proc:
            LOG.info("Launched command: %s", " ".join(cmd))

            start_time = time.time()
            stop_time = start_time + kwargs["run_timeout"]
            return_code = None
            wait_time = 1
            while time.time() < stop_time:
                return_code = proc.poll()
                if return_code is None:
                    if time.time() - start_time > 1:
                        LOG.info("%s is still running. Waiting %d seconds more.", cmd[0], stop_time - time.time())
                    wait_time = wait_time * 2 if wait_time < 10 else 10
                    time.sleep(wait_time)
                else:
                    break

            cout, cerr = proc.communicate()

            comment = f"{comment_salt} exited with code {return_code}.\n"
            comment += f"**`/dev/stdout`**:\n```\n{cout.decode() or 'No output'}\n```\n"
            comment += f"**`/dev/stderr`**:\n```\n{cerr.decode() or 'No output'}\n```\n"

            sys.stdout.write(cout.decode())
            sys.stderr.write(cerr.decode())
            sys.exit(proc.returncode)

    except FileNotFoundError as err:
        LOG.exception(err)
        comment = f"{comment_salt} failed to start.\n"
        comment += f"Stack trace:\n```\n{traceback.format_exc()}\n```\n"
        sys.exit(1)

    finally:
        _upsert_comment(pull_request, comment, comment_salt)


def _upsert_comment(pull_request, comment, comment_salt):
    existing_comment = next((item for item in pull_request.comments if item.body.startswith(comment_salt)), None)
    if existing_comment:
        pull_request.edit_comment(existing_comment, comment)
    else:
        pull_request.publish_comment(comment)
