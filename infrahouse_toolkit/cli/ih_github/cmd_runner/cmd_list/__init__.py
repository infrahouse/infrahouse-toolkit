"""
.. topic:: ``ih-github runner list``

    A ``ih-github runner list`` subcommand.

    See ``ih-github runner list --help`` for more details.
"""

import json
import logging

import click
from requests import get

LOG = logging.getLogger()


@click.command(
    name="list",
)
@click.pass_context
def cmd_list(ctx, *args, **kwargs):
    """
    List self-hosted runners

    """
    LOG.debug("args = %s", args)
    LOG.debug("kwargs = %s", kwargs)
    LOG.debug(ctx.args)
    github_token = ctx.obj["github_token"]
    org = ctx.obj["org"]
    response = get(
        f"https://api.github.com/orgs/{org}/actions/runners",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {github_token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=30,
    )
    print(json.dumps(response.json()))
