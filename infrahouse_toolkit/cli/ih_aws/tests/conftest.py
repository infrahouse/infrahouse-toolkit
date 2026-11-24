"""Fixtures for ``ih-aws`` tests."""

from unittest import mock

import boto3
import pytest
from moto import mock_aws

from infrahouse_toolkit.cli.ih_aws.tests.moto_asg import REGION, MotoASG


@pytest.fixture(name="aws")
def _aws(monkeypatch):
    """
    Moto, with the region from the environment rather than from ``--aws-region``, as on an instance.

    ``setup_logging()`` is patched out, because it would replace pytest's log handlers.
    """
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.delenv("AWS_SESSION_TOKEN", raising=False)
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.setenv("AWS_DEFAULT_REGION", REGION)
    with mock_aws(), mock.patch("infrahouse_toolkit.cli.ih_aws.setup_logging"):
        yield


@pytest.fixture(name="image_id")
def _image_id(aws) -> str:  # pylint: disable=unused-argument
    """An AMI that moto knows."""
    return boto3.client("ec2", region_name=REGION).describe_images(Owners=["amazon"])["Images"][0]["ImageId"]


@pytest.fixture(name="asg")
def _asg(image_id) -> MotoASG:
    """An autoscaling group of two instances."""
    return MotoASG(image_id)
