"""
Fixtures of the integration test: the candidate under test, and a jumphost that installs it.
"""

import json
import logging
from os import path as osp
from typing import Iterator

import pytest
from infrahouse_core.logging import setup_logging
from pytest_infrahouse import terraform_apply

from tests.integration.apt import (
    PACKAGE,
    TESTING_REPO_CODENAME,
    TESTING_REPO_URL,
    PackagesIndex,
)
from tests.integration.aws import CandidateGroup

LOG = logging.getLogger(__name__)
setup_logging()

TERRAFORM_DIR = osp.join(osp.dirname(__file__), "terraform")

# terraform-aws-jumphost boots an x86_64 AMI (data.aws_ami.ubuntu_pro).
ARCHITECTURE = "amd64"


def pytest_addoption(parser: pytest.Parser) -> None:
    """
    Add ``--toolkit-version``.

    :param parser: pytest's option parser.
    :type parser: pytest.Parser
    """
    parser.addoption(
        "--toolkit-version",
        action="store",
        default=None,
        help=(
            "The infrahouse-toolkit version to test, as the testing repository lists it, "
            "for example 2.68.3+candidate.259.1-1. By default, the newest one for amd64."
        ),
    )


@pytest.fixture(name="testing_repo", scope="session")
def _testing_repo() -> PackagesIndex:
    """
    :return: The testing repository's ``Packages`` index for the instance's architecture.
    """
    return PackagesIndex(TESTING_REPO_URL, TESTING_REPO_CODENAME, ARCHITECTURE)


@pytest.fixture(name="toolkit_version", scope="session")
def _toolkit_version(request: pytest.FixtureRequest, testing_repo: PackagesIndex) -> str:
    """
    The version under test: ``--toolkit-version``, or the newest candidate in the testing repository.

    :return: The Debian version, for example ``2.68.3+candidate.259.1-1``.
    :raise LookupError: If the testing repository doesn't list it.
    """
    requested = request.config.getoption("--toolkit-version")
    if requested:
        version = testing_repo.require(PACKAGE, requested)
        LOG.info("Testing %s %s, given by --toolkit-version.", PACKAGE, version)
    else:
        version = testing_repo.newest(PACKAGE)
        LOG.info("Testing %s %s, the newest in %s.", PACKAGE, version, testing_repo.url)
    return version


@pytest.fixture(name="candidate_group", scope="session")
def _candidate_group(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    service_network: dict,
    subzone: dict,
    toolkit_version: str,
    aws_region: str,
    test_role_arn: str,
    keep_after: bool,
    boto3_session,
) -> Iterator[CandidateGroup]:
    """
    Deploy the jumphost with the testing repository and the version under test, and destroy it afterwards unless
    ``--keep-after`` is given.

    :return: The jumphost's Auto Scaling group.
    """
    tf_vars = {
        "region": aws_region,
        "subnet_private_ids": service_network["subnet_private_ids"]["value"],
        "subnet_public_ids": service_network["subnet_public_ids"]["value"],
        "test_zone_id": subzone["subzone_id"]["value"],
        "testing_repo_codename": TESTING_REPO_CODENAME,
        "testing_repo_url": TESTING_REPO_URL,
        "toolkit_version": toolkit_version,
    }
    if test_role_arn:
        tf_vars["role_arn"] = test_role_arn
    with open(osp.join(TERRAFORM_DIR, "terraform.tfvars.json"), "w", encoding="utf-8") as tf_vars_file:
        json.dump(tf_vars, tf_vars_file, indent=2)

    with terraform_apply(
        TERRAFORM_DIR,
        destroy_after=not keep_after,
        json_output=True,
        var_file="terraform.tfvars.json",
    ) as tf_output:
        yield CandidateGroup(tf_output["asg_name"]["value"], session=boto3_session, region=aws_region)
