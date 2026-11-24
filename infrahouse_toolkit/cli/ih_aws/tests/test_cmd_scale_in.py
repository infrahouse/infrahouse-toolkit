"""
Contract tests for ``ih-aws autoscaling scale-in``: the CLI, through infrahouse-core, against moto.

moto implements ``SetInstanceProtection``, so nothing is intercepted. The tests check the protection moto
records for every instance of the group, which is right only if the call named the right group, the right
instance and the right setting.

These tests replay issue #206: v2.57.0 passed ``instance_id`` positionally to ``ASGInstance``, which
infrahouse-core 0.23.6 to 0.27.0 don't accept, and every ``scale-in`` failed with a ``TypeError``.
"""

from unittest import mock

import pytest
from click.testing import CliRunner, Result

from infrahouse_toolkit.cli.ih_aws import ih_aws

# Well-formed, but no such instance exists in moto.
UNKNOWN_INSTANCE_ID = "i-0123456789abcdef0"


@pytest.mark.parametrize("action, protected", [("enable-protection", True), ("disable-protection", False)])
def test_explicit_instance(asg, action, protected):
    """The given instance's protection changes; the other instance's doesn't."""
    asg.protect_all(not protected)
    target, other = asg.instance_ids

    cli = _scale_in(action, target)

    assert cli.exit_code == 0, cli.output
    assert asg.scale_in_protection == {target: protected, other: not protected}


@pytest.mark.parametrize("action, protected", [("enable-protection", True), ("disable-protection", False)])
def test_local_instance(asg, action, protected):
    """Without an instance id, the local instance's protection changes."""
    asg.protect_all(not protected)
    target, other = asg.instance_ids

    with mock.patch("infrahouse_core.aws.ec2_instance.ec2_metadata") as metadata:
        metadata.instance_id = target
        cli = _scale_in(action)

    assert cli.exit_code == 0, cli.output
    assert asg.scale_in_protection == {target: protected, other: not protected}


@pytest.mark.parametrize("action", ["enable-protection", "disable-protection"])
def test_unknown_instance(asg, caplog, action):
    """An instance that doesn't exist exits 1 with the AWS error logged, not a traceback, and changes nothing."""
    before = asg.scale_in_protection

    cli = _scale_in(action, UNKNOWN_INSTANCE_ID)

    assert cli.exit_code == 1
    assert isinstance(cli.exception, SystemExit)
    assert "InvalidInstanceID.NotFound" in caplog.text
    assert asg.scale_in_protection == before


def _scale_in(*args: str) -> Result:
    """
    Run ``ih-aws autoscaling scale-in [args]``.

    :param args: Arguments of ``scale-in``.
    :return: The CLI result.
    """
    return CliRunner().invoke(ih_aws, ["autoscaling", "scale-in", *args])
