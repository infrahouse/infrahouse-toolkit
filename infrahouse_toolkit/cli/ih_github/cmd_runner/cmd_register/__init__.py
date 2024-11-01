"""
.. topic:: ``ih-github runner register``

    A ``ih-github runner register`` subcommand.

    See ``ih-github runner register --help`` for more details.
"""

import logging
from os import path as osp
from subprocess import run

import boto3
import click
from requests import post

from infrahouse_toolkit.cli.ih_secrets.cmd_get import get_secret

LOG = logging.getLogger()
AR_URL = "https://github.com/actions/runner/releases/download/v2.314.1/actions-runner-linux-x64-2.314.1.tar.gz"


@click.command(
    name="register",
)
@click.option(
    "--actions-runner-code-path",
    help=f"Path to a directory with the actions-runner code. You can download it from {AR_URL}",
    show_default=True,
    default="/tmp/actions-runner-linux",
)
@click.option(
    "--label",
    help="Add a label to the runner.",
    multiple=True,
)
@click.argument("URL")
@click.pass_context
def cmd_register(ctx, **kwargs):
    """
    register a self-hosted runner. A given URL can be either org or a repo address.

    """
    github_token = ctx.obj["github_token"]
    org = ctx.obj["org"]
    registration_token_secret = ctx.obj["registration_token_secret"]

    if registration_token_secret:
        token = get_secret(boto3.client("secretsmanager"), registration_token_secret)

    else:
        response = post(
            f"https://api.github.com/orgs/{org}/actions/runners/registration-token",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {github_token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30,
        )
        response.raise_for_status()
        token = response.json()["token"]

    cmd = [
        osp.join(kwargs["actions_runner_code_path"], "config.sh"),
        "--url",
        kwargs["url"],
        "--token",
        token,
        "--unattended",
        "--disableupdate",
    ]
    if kwargs["label"]:
        cmd.extend(["--labels", ",".join(kwargs["label"])])
    LOG.debug("Executing %s", " ".join(cmd))
    run(
        cmd,
        check=True,
        env={
            "RUNNER_ALLOW_RUNASROOT": "microsoft_sux",
            "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        },
    )
