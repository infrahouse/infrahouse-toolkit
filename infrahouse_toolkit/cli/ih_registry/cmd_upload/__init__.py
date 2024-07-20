"""
.. topic:: ``ih-registry upload``

    A ``ih-registry upload`` subcommand.

    See ``ih-registry upload`` for more details.
"""

from logging import getLogger
from os import path as osp
from shutil import make_archive
from tempfile import TemporaryDirectory

import boto3
import click
import git
import requests

LOG = getLogger()


@click.command(name="upload")
@click.option(
    "--registry-url",
    help="InfraHouse Terraform Registry address",
    default="https://registry.infrahouse.com",
    show_default=True,
)
@click.option(
    "--dynamodb-table",
    help="Name of a DynamoDB table with deployment API keys",
    default="DeployKeys",
    show_default=True,
)
@click.option(
    "--deploy-key",
    help="Deployment API keys. By default, read from the DynamoDB table, specified by --dynamodb-table",
    default=None,
)
@click.option(
    "--module-name",
    help="Terraform module name in format <namespace>/<name>/<provider>. For example, infrahouse/cloud-init/aws",
)
@click.option(
    "--namespace",
    help="Terraform registry namespace. "
    "If --module-name isn't specified, this namespace will be used to construct the module name.",
    default="infrahouse",
    show_default=True,
)
@click.option(
    "--provider",
    help="Terraform provider name. "
    "If --module-name isn't specified, this provider name will be used to construct the module name.",
    default="aws",
    show_default=True,
)
@click.option(
    "--module-version",
    help="Terraform module name version. Must follow semantic versioning convention",
)
@click.option(
    "--module-path",
    help="Path to a directory with the Terraform module. The directory includes main.tf and other files",
    default=".",
    show_default=True,
)
def cmd_upload(**kwargs):
    """
    Upload Terraform module to the InfraHouse Terraform Registry
    """
    module_path = kwargs["module_path"]
    module_name = kwargs["module_name"] or "/".join(
        [
            kwargs["namespace"],
            _detect_module_name(module_path),
            kwargs["provider"],
        ]
    )
    module_version = kwargs["module_version"] or _detect_latest_tag(module_path)
    url = f"{kwargs['registry_url']}/terraform/modules/v1/{module_name}/{module_version}"
    LOG.debug("Uploading to %s", url)
    # 1 / 0
    api_key = kwargs["deploy_key"] or _detect_api_key(kwargs["dynamodb_table"], module_name)
    with TemporaryDirectory() as tmp_dir:
        LOG.debug("Archiving directory %s into directory %s", module_path, tmp_dir)
        archive_name = make_archive(osp.join(tmp_dir, "module"), "zip", kwargs["module_path"])
        LOG.debug("Archive %s", archive_name)
        with open(archive_name, "rb") as archive_desc:
            response = requests.post(
                url=url, headers={"x-api-key": api_key}, files={"archive": archive_desc.read()}, timeout=300
            )
            response.raise_for_status()
            LOG.info("Server response: code %d, body: %s", response.status_code, response.text or "empty")


def _detect_api_key(dynamodb_table: str, module_name: str) -> str:
    client = boto3.client("dynamodb")
    response = client.get_item(
        TableName=dynamodb_table,
        Key={
            "id": {
                "S": "-".join(module_name.split("/")),
            }
        },
    )
    return response["Item"]["key"]["S"]


def _detect_latest_tag(repo_path: str) -> str:
    repo = git.Repo(repo_path)
    tags = sorted(repo.tags, key=lambda t: t.commit.committed_datetime)
    LOG.debug("tags in %s: %s", repo_path, tags)
    latest_tag = tags[-1]
    return latest_tag.name


def _detect_module_name(module_path: str) -> str:
    path = osp.basename(osp.abspath(module_path))
    path_parts = path.split("-")
    path_parts.pop(0)
    path_parts.pop(0)
    return "-".join(path_parts)
