"""
.. topic:: ``ih-github backup``

    A ``ih-github backup`` subcommand.

    See ``ih-github backup --help`` for more details.
"""

import logging
from datetime import datetime
from multiprocessing import Pool, set_start_method
from os import path as osp
from shutil import rmtree
from urllib.parse import urlparse

import click
import requests
from github import GithubIntegration
from github.Consts import MAX_JWT_EXPIRY

from infrahouse_toolkit import DEFAULT_OPEN_ENCODING
from infrahouse_toolkit.aws import get_client, get_secret
from infrahouse_toolkit.cli.ih_github.exceptions import IHVariableNotFound
from infrahouse_toolkit.cli.utils import (
    check_dependencies,
    execute,
    mkdir_p,
    retry,
    tmpfs_s3,
)
from infrahouse_toolkit.logging import setup_logging

LOG = logging.getLogger()
GH_APP_ID = "1016509"


def _get_variable(name, gh_token, org_name):
    url = f"https://api.github.com/orgs/{org_name}/actions/variables/{name}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {gh_token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    response = requests.get(url, headers=headers, timeout=600)
    if response.status_code == 404:
        raise IHVariableNotFound(f"Variable {name} doesn't exist.")

    return response.json()["value"]


def _get_backup_bucket(gh_token, org_name):
    return _get_variable("INFRAHOUSE_BACKUP_BUCKET", gh_token, org_name)


def _get_backup_role(gh_token, org_name):
    return _get_variable("INFRAHOUSE_BACKUP_ROLE", gh_token, org_name)


def _get_org_name(github_client, installation_id):
    url = f"https://api.github.com/app/installations/{installation_id}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {github_client.create_jwt()}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    response = requests.get(url, headers=headers, timeout=600)
    return response.json()["account"]["login"]


@click.command(
    name="backup",
)
@click.option(
    "--app-key-url",
    help="URL to fetch the GitHub App key. Supports schemes file://, secretsmanager://",
    default=None,
    required=True,
)
@click.option(
    "--only-installation-id",
    help="Backup only a specified installation id.",
    type=click.INT,
)
@click.option(
    "--tmp-volume-size",
    help="Size of in-memory temporary file system.",
    default="512M",
    show_default=True,
)
@click.pass_context
def cmd_backup(ctx, **kwargs):
    """
    infrahouse-github-backup implementation.

    For each GitHub App installation,

    * Reads configuration from the Org: IAM role, S3 bucket, list of repos
    * Assumes, the IAM role
    * Mounts the S3 Bucket
    * Syncs each repo to the S3 bucket.
    """
    check_dependencies(["s3fs"])
    app_key_url = urlparse(kwargs["app_key_url"])
    LOG.debug("GitHub App key URL: %r", app_key_url)
    if app_key_url.scheme == "file":
        with open(f"/{app_key_url.netloc}{app_key_url.path}", "r", encoding=DEFAULT_OPEN_ENCODING) as key_file:
            app_key = key_file.read()
    elif app_key_url.scheme == "secretsmanager":
        app_key = get_secret(get_client("secretsmanager"), app_key_url.netloc)
    else:
        raise RuntimeError(f"Unsupported App key URL scheme {app_key_url.scheme}")

    github_client = GithubIntegration(GH_APP_ID, app_key, jwt_expiry=MAX_JWT_EXPIRY)
    set_start_method("spawn")
    for installation in github_client.get_installations():
        LOG.info("Processing installation %r", installation)
        if installation.target_type != "Organization":
            LOG.warning(
                "Installation %d is type %s, which is not Organization. It's not supported.",
                installation.id,
                installation.target_type,
            )
            continue
        org_name = _get_org_name(github_client, installation.id)
        if kwargs["only_installation_id"] and kwargs["only_installation_id"] != installation.id:
            LOG.warning(
                "Skipping installation id %d (%s) because --only-installation-id %d was requested.",
                installation.id,
                org_name,
                kwargs["only_installation_id"],
            )
            continue
        token = github_client.get_access_token(installation_id=installation.id).token
        try:
            bucket_name = _get_backup_bucket(token, org_name)
            with tmpfs_s3(
                bucket_name, role_arn=_get_backup_role(token, org_name), volume_size=kwargs["tmp_volume_size"]
            ) as path:
                with Pool() as pool:
                    pool.starmap(
                        _backup_repo, [(repo, path, token, ctx.obj["debug"]) for repo in installation.get_repos()]
                    )
            LOG.info("Backing up installation %r is done.", installation)

        except IHVariableNotFound as err:
            LOG.error(err)
            LOG.error("Organization %s is not fully configured.", org_name)


def _backup_repo(repository, dst_path, token, debug=False):
    setup_logging(debug=debug)
    LOG.debug("Backing up repository %s", repository)
    mkdir_p(osp.join(dst_path, str(repository.owner.login)))
    suffix = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    retry(
        execute,
        (
            [
                "gh",
                "repo",
                "clone",
                repository.full_name,
                osp.join(repository.full_name, suffix),
                "--",
                "--mirror",
            ],
        ),
        {
            "cwd": dst_path,
            "env": {
                "PATH": "/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:",
                "GH_TOKEN": token,
            },
            "exit_on_error": False,
        },
    )
    execute(
        ["tar", "zcf", f"{suffix}.tar.gz", suffix],
        cwd=osp.join(dst_path, str(repository.full_name)),
        env={
            "PATH": "/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:",
        },
    )
    rmtree(osp.join(dst_path, str(repository.full_name), suffix))
