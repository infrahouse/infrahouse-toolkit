"""
.. topic:: ``ih-github scan``

    A ``ih-github scan`` subcommand.

    See ``ih-github scan --help`` for more details.
"""

import logging

import click

from infrahouse_toolkit.cli.utils import check_dependencies

LOG = logging.getLogger()
DEPENDENCIES = ["osv-scanner"]


@click.command(
    name="scan",
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
@click.option("--github-token", help="Personal access token for GitHub.", envvar="GITHUB_TOKEN")
@click.option("--repo", help="GitHub repository name in short format e.g. infrahouse-toolkit.")
@click.option("--pull-request", help="GitHub pull request number.", type=click.INT)
@click.pass_context
def cmd_scan(ctx, *args, **kwargs):
    """
    Scan the current directory for dependency vulnerabilities.
    If found, publish a report as a pull request comment.

    For instance
    """
    LOG.debug("args = %s", args)
    LOG.debug("kwargs = %s", kwargs)
    cmd_args = ctx.args
    LOG.debug("cmd_args = %s", cmd_args)
    check_dependencies(DEPENDENCIES)
    # pull_request = GitHubPR(kwargs["repo"], kwargs["pull_request_number"], github_token=kwargs["github_token"])
    # try:
    #     with Popen(cmd, stderr=PIPE, stdout=PIPE) as proc:
    #         LOG.info("Launched command: %s", " ".join(cmd))
    #
    #         start_time = time.time()
    #         stop_time = start_time + kwargs["run_timeout"]
    #         return_code = None
    #         wait_time = 1
    #         while time.time() < stop_time:
    #             return_code = proc.poll()
    #             if return_code is None:
    #                 if time.time() - start_time > 1:
    #                     LOG.info("%s is still running. Waiting %d seconds more.", cmd[0], stop_time - time.time())
    #                 wait_time = wait_time * 2 if wait_time < 10 else 10
    #                 time.sleep(wait_time)
    #             else:
    #                 break
    #
    #         cout, cerr = proc.communicate()
    #
    #         comment = f"Command `{' '.join(cmd)}` exited with code {return_code}.\n"
    #         comment += f"**Standard output**:\n```\n{cout.decode() or 'No output'}\n```\n"
    #         comment += f"**Standard error**:\n```\n{cerr.decode() or 'No output'}\n```\n"
    #
    #         sys.stdout.write(cout.decode())
    #         sys.stderr.write(cerr.decode())
    #         sys.exit(proc.returncode)
    #
    # except FileNotFoundError as err:
    #     LOG.exception(err)
    #     comment = f"Command `{' '.join(cmd)}` failed to start.\n"
    #     comment += f"Stack trace:\n```\n{traceback.format_exc()}\n```\n"
    #     sys.exit(1)
    #
    # finally:
    #     pull_request.publish_comment(comment)
