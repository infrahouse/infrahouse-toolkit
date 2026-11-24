"""
Contract tests for ``ih-aws autoscaling complete``: the CLI, through infrahouse-core, against moto.

moto doesn't implement ``CompleteLifecycleAction``, so that operation alone is intercepted and its
parameters are asserted. Everything else, e.g. finding the instance's autoscaling group, runs in moto.
"""

from unittest import mock

import pytest
from botocore.client import BaseClient
from click.testing import CliRunner, Result

from infrahouse_toolkit.cli.ih_aws import ih_aws
from infrahouse_toolkit.cli.ih_aws.tests.intercepted_operation import (
    InterceptedOperation,
)

# Well-formed, but no such instance exists in moto.
UNKNOWN_INSTANCE_ID = "i-0123456789abcdef0"


@pytest.mark.parametrize("options, result", [([], "CONTINUE"), (["--result", "ABANDON"], "ABANDON")])
def test_explicit_instance(asg, options, result):
    """The lifecycle action of the given instance completes, in that instance's group, with the given result."""
    api = InterceptedOperation("CompleteLifecycleAction")
    instance_id = asg.instance_ids[1]

    cli = _complete(api, *options, "terminating", instance_id)

    assert cli.exit_code == 0, cli.output
    assert api.calls == [
        {
            "LifecycleHookName": "terminating",
            "AutoScalingGroupName": asg.name,
            "LifecycleActionResult": result,
            "InstanceId": instance_id,
        }
    ]


def test_local_instance(asg):
    """Without an instance id, the lifecycle action of the local instance completes."""
    api = InterceptedOperation("CompleteLifecycleAction")
    instance_id = asg.instance_ids[0]

    with mock.patch("infrahouse_core.aws.ec2_instance.ec2_metadata") as metadata:
        metadata.instance_id = instance_id
        cli = _complete(api, "launching")

    assert cli.exit_code == 0, cli.output
    assert api.calls == [
        {
            "LifecycleHookName": "launching",
            "AutoScalingGroupName": asg.name,
            "LifecycleActionResult": "CONTINUE",
            "InstanceId": instance_id,
        }
    ]


def test_api_error(asg, caplog):
    """An error from ``CompleteLifecycleAction`` exits 1 with the error logged, not a traceback."""
    api = InterceptedOperation("CompleteLifecycleAction", error_code="ValidationError")

    cli = _complete(api, "terminating", asg.instance_ids[0])

    assert cli.exit_code == 1
    assert isinstance(cli.exception, SystemExit)
    assert len(api.calls) == 1
    assert "ValidationError" in caplog.text


def test_unknown_instance(asg, caplog):  # pylint: disable=unused-argument
    """An instance that doesn't exist exits 1 with the AWS error logged, and completes nothing."""
    api = InterceptedOperation("CompleteLifecycleAction")

    cli = _complete(api, "terminating", UNKNOWN_INSTANCE_ID)

    assert cli.exit_code == 1
    assert isinstance(cli.exception, SystemExit)
    assert "InvalidInstanceID.NotFound" in caplog.text
    assert not api.calls


def _complete(api: InterceptedOperation, *args: str) -> Result:
    """
    Run ``ih-aws autoscaling complete [args]`` with ``CompleteLifecycleAction`` answered by ``api``.

    :param api: The stand-in for ``CompleteLifecycleAction``.
    :param args: Arguments and options of ``complete``.
    :return: The CLI result.
    """
    with mock.patch.object(BaseClient, "_make_api_call", autospec=True, side_effect=api.make_api_call):
        return CliRunner().invoke(ih_aws, ["autoscaling", "complete", *args])
