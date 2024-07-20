"""
.. topic:: ``ih-github runner deregister``

    A ``ih-github runner deregister`` subcommand.

    See ``ih-github runner deregister --help`` for more details.
"""

import logging

import click
from requests import delete

LOG = logging.getLogger()


@click.command(
    name="deregister",
)
@click.argument("runner_id", type=click.INT)
@click.pass_context
def cmd_deregister(ctx, **kwargs):
    """
    deregister a self-hosted runner.
    """
    github_token = ctx.obj["github_token"]
    org = ctx.obj["org"]

    response = delete(
        f"https://api.github.com/orgs/{org}/actions/runners/{kwargs['runner_id']}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {github_token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=30,
    )
    response.raise_for_status()
    LOG.info("Runner %d is successfully deregistered.", kwargs["runner_id"])
