"""Unit tests for :py:mod:`infrahouse_toolkit.cli.ih_aws.cmd_autoscaling.cmd_cancel_instance_refresh`."""

import logging
from unittest import mock

import boto3
from botocore.client import BaseClient
from click.testing import CliRunner, Result
from requests import ConnectTimeout

from infrahouse_toolkit.cli.ih_aws import ih_aws
from infrahouse_toolkit.cli.ih_aws.tests.cancel_instance_refresh_api import (
    CancelInstanceRefreshAPI,
)
from infrahouse_toolkit.cli.ih_aws.tests.moto_asg import REGION

ASG_NAME = "web"


def test_explicit_asg_name(aws):  # pylint: disable=unused-argument
    """The refresh of the named group is cancelled."""
    api = CancelInstanceRefreshAPI()

    result = _cancel(api, ASG_NAME)

    assert result.exit_code == 0, result.output
    assert api.calls == [{"AutoScalingGroupName": ASG_NAME}]


def test_local_instance(asg):
    """Without a group name, the refresh of the local instance's group is cancelled."""
    api = CancelInstanceRefreshAPI()

    with mock.patch("infrahouse_core.aws.ec2_instance.ec2_metadata") as metadata:
        metadata.instance_id = asg.instance_ids[0]
        result = _cancel(api)

    assert result.exit_code == 0, result.output
    assert api.calls == [{"AutoScalingGroupName": asg.name}]


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


def test_instance_not_in_asg(image_id, caplog):
    """An instance outside an autoscaling group exits 1 with a clear error, not a traceback."""
    ec2 = boto3.client("ec2", region_name=REGION)
    instance_id = ec2.run_instances(ImageId=image_id, MinCount=1, MaxCount=1)["Instances"][0]["InstanceId"]
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
