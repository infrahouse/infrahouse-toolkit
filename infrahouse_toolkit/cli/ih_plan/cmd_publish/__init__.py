"""
.. topic:: ``ih-plan publish``

    A ``ih-plan publish`` subcommand.

    See ``ih-plan publish --help`` for more details.
"""

import click

from infrahouse_toolkit import DEFAULT_OPEN_ENCODING
from infrahouse_toolkit.cli.lib import get_backend_key, get_bucket
from infrahouse_toolkit.terraform import RunOutput, TFStatus, parse_plan
from infrahouse_toolkit.terraform.backends import TFS3Backend
from infrahouse_toolkit.terraform.githubpr import GitHubPR
from infrahouse_toolkit.terraform.status import strip_lines


@click.command(name="publish")
@click.option("--github-token", help="Personal access token for GitHub.", envvar="GITHUB_TOKEN")
@click.option(
    "--tf-exit-code", help="With what code number the terraform plan command exited.", default=0, show_default=True
)
@click.option(
    "--private-gist/--public-gist",
    help="When the comment is too large and the tool needs to publish the comment as a gist,"
    "should it be private or public.",
    default=True,
    show_default=True,
)
@click.argument("repo")
@click.argument("pull_request_number")
@click.argument("tf_plan_stdout", type=click.Path(exists=True))
@click.argument("tf_plan_stderr", type=click.Path(exists=True))
@click.pass_context
def cmd_publish(*args, **kwargs):
    """
    Publish Terraform plan to GitHub pull request.

    Example:

        ih-plan publish infrahouse8/github-control 33 plan.stdout plan.stderr

    Here:

    \b
        * ``infrahouse8/github-control`` - full repository name.
        * ``33`` - pull request number.
        * ``plan.stdout`` - file with ``terraform plan`` output.
        * ``plan.stderr`` - file with ``terraform plan`` error output.

    """
    ctx = args[0]

    with open(kwargs["tf_plan_stdout"], encoding=DEFAULT_OPEN_ENCODING) as fp_stdout, open(
        kwargs["tf_plan_stderr"], encoding=DEFAULT_OPEN_ENCODING
    ) as fp_stderr:
        stdout = strip_lines(fp_stdout.read(), "::debug::")
        stderr = strip_lines(fp_stderr.read(), "::debug::")

        counts, resources = parse_plan(stdout)
        backend = TFS3Backend(
            ctx.obj["bucket"] or get_bucket(ctx.obj["tf_backend_file"]),
            get_backend_key(ctx.obj["tf_backend_file"]),
        )
        status = TFStatus(
            backend,
            kwargs["tf_exit_code"] == 0,
            counts,
            RunOutput(stdout, stderr),
            affected_resources=resources,
        )
        pull_request = GitHubPR(kwargs["repo"], int(kwargs["pull_request_number"]), github_token=kwargs["github_token"])
        comment = pull_request.find_comment_by_backend(backend)
        if comment:
            pull_request.edit_comment(comment, status.comment, private_gist=kwargs["private_gist"])
        else:
            pull_request.publish_comment(status.comment, private_gist=kwargs["private_gist"])
