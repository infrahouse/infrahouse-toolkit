"""Unit tests for :py:mod:`infrahouse_toolkit.cli.ih_aws.cmd_autoscaling.cmd_cancel_instance_refresh`."""

import logging
from unittest import mock

import boto3
import pytest
from botocore.client import BaseClient
from click.testing import CliRunner, Result
from moto import mock_aws
from requests import ConnectTimeout

from infrahouse_toolkit.cli.ih_aws import ih_aws
from infrahouse_toolkit.cli.ih_aws.tests.cancel_instance_refresh_api import (
    CancelInstanceRefreshAPI,
)

REGION = "us-east-1"
ASG_NAME = "web"


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


def test_explicit_asg_name(aws):  # pylint: disable=unused-argument
    """The refresh of the named group is cancelled."""
    api = CancelInstanceRefreshAPI()

    result = _cancel(api, ASG_NAME)

    assert result.exit_code == 0, result.output
    assert api.calls == [{"AutoScalingGroupName": ASG_NAME}]


def test_local_instance(aws):  # pylint: disable=unused-argument
    """Without a group name, the refresh of the local instance's group is cancelled."""
    instance_id = _instance_in_asg()
    api = CancelInstanceRefreshAPI()

    with mock.patch("infrahouse_core.aws.ec2_instance.ec2_metadata") as metadata:
        metadata.instance_id = instance_id
        result = _cancel(api)

    assert result.exit_code == 0, result.output
    assert api.calls == [{"AutoScalingGroupName": ASG_NAME}]


def test_no_active_refresh(aws, caplog):  # pylint: disable=unused-argument
    """A group without an active instance refresh exits 0 and says so in the log."""
    api = CancelInstanceRefreshAPI(error_code="ActiveInstanceRefreshNotFound")

    with caplog.at_level(logging.INFO):
        result = _cancel(api, ASG_NAME)

    assert result.exit_code == 0, result.output
    assert len(api.calls) == 1
    assert "ActiveInstanceRefreshNotFound" in caplog.text


def test_api_error(aws, caplog):  # pylint: disable=unused-argument
    """Any other API error exits 1 with the error logged."""
    api = CancelInstanceRefreshAPI(error_code="AccessDenied")

    result = _cancel(api, ASG_NAME)

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert "AccessDenied" in caplog.text


def test_instance_not_in_asg(aws, caplog):  # pylint: disable=unused-argument
    """An instance outside an autoscaling group exits 1 with a clear error, not a traceback."""
    ec2 = boto3.client("ec2", region_name=REGION)
    instance_id = ec2.run_instances(ImageId=_image_id(), MinCount=1, MaxCount=1)["Instances"][0]["InstanceId"]
    api = CancelInstanceRefreshAPI()

    with mock.patch("infrahouse_core.aws.ec2_instance.ec2_metadata") as metadata:
        metadata.instance_id = instance_id
        result = _cancel(api)

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert f"Instance {instance_id} is not a member of an autoscaling group." in caplog.text
    assert not api.calls


def test_no_instance_metadata(aws, caplog):  # pylint: disable=unused-argument
    """Without EC2 instance metadata, it exits 1 with the error logged, not a traceback."""
    api = CancelInstanceRefreshAPI()

    with mock.patch("infrahouse_core.aws.ec2_instance.ec2_metadata") as metadata:
        type(metadata).instance_id = mock.PropertyMock(side_effect=ConnectTimeout("no instance metadata"))
        result = _cancel(api)

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert "no instance metadata" in caplog.text
    assert not api.calls


def _cancel(api: CancelInstanceRefreshAPI, *args: str) -> Result:
    """
    Run ``ih-aws autoscaling cancel-instance-refresh [args]`` with ``CancelInstanceRefresh`` answered by ``api``.
    """
    with mock.patch.object(BaseClient, "_make_api_call", autospec=True, side_effect=api.make_api_call):
        return CliRunner().invoke(ih_aws, ["autoscaling", "cancel-instance-refresh", *args])


def _image_id() -> str:
    """
    :return: An AMI that moto knows.
    """
    return boto3.client("ec2", region_name=REGION).describe_images(Owners=["amazon"])["Images"][0]["ImageId"]


def _instance_in_asg() -> str:
    """
    Create an autoscaling group of one instance.

    :return: The instance id.
    """
    boto3.client("ec2", region_name=REGION).create_launch_template(
        LaunchTemplateName=ASG_NAME, LaunchTemplateData={"ImageId": _image_id(), "InstanceType": "t3.micro"}
    )
    autoscaling = boto3.client("autoscaling", region_name=REGION)
    autoscaling.create_auto_scaling_group(
        AutoScalingGroupName=ASG_NAME,
        LaunchTemplate={"LaunchTemplateName": ASG_NAME},
        MinSize=1,
        MaxSize=1,
        DesiredCapacity=1,
        AvailabilityZones=[f"{REGION}a"],
    )
    groups = autoscaling.describe_auto_scaling_groups(AutoScalingGroupNames=[ASG_NAME])["AutoScalingGroups"]
    return groups[0]["Instances"][0]["InstanceId"]
