"""
.. topic:: ``ih-github runner is-registered``

    A ``ih-github runner is-registered`` subcommand.

    See ``ih-github runner is-registered --help`` for more details.
"""

import json
import logging
import sys

import click
from requests import get

LOG = logging.getLogger()


@click.command(
    name="is-registered",
)
@click.argument("name")
@click.pass_context
def cmd_is_registered(ctx, **kwargs):
    """
    Check if a runner with the given name is already registered.

    Exit code is zero if registered. Otherwise, 1.
    """
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
    for runner in response.json()["runners"]:
        if runner["name"] == kwargs["name"]:
            LOG.info("Runner %s is registered", kwargs["name"])
            print(json.dumps(runner, indent=4))
            sys.exit(0)

    LOG.info("Runner %s is unregistered", kwargs["name"])
    sys.exit(1)
