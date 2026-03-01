"""Tests for :class:`infrahouse_toolkit.aws.resource_discovery.SecurityGroupRule`."""

from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from infrahouse_toolkit.aws.resource_discovery import SecurityGroupRule


@pytest.fixture()
def mock_ec2_client() -> MagicMock:
    """Return a mock EC2 client."""
    return MagicMock()


@pytest.fixture()
def sgr(mock_ec2_client: MagicMock) -> SecurityGroupRule:
    """Return a SecurityGroupRule with a mocked EC2 client."""
    rule = SecurityGroupRule("sgr-0abcdef1234567890", region="us-east-1")
    rule._client_instance = mock_ec2_client
    return rule


def test_exists_returns_true_when_present(sgr: SecurityGroupRule, mock_ec2_client: MagicMock) -> None:
    """Rule that exists should return True."""
    mock_ec2_client.describe_security_group_rules.return_value = {
        "SecurityGroupRules": [{"SecurityGroupRuleId": "sgr-0abcdef1234567890", "GroupId": "sg-123", "IsEgress": False}]
    }
    assert sgr.exists is True


def test_exists_returns_false_when_not_found(sgr: SecurityGroupRule, mock_ec2_client: MagicMock) -> None:
    """Rule not found should return False."""
    mock_ec2_client.describe_security_group_rules.side_effect = ClientError(
        {"Error": {"Code": "InvalidSecurityGroupRuleId.NotFound", "Message": "not found"}},
        "DescribeSecurityGroupRules",
    )
    assert sgr.exists is False


def test_exists_raises_on_unexpected_error(sgr: SecurityGroupRule, mock_ec2_client: MagicMock) -> None:
    """Unexpected ClientError should propagate."""
    mock_ec2_client.describe_security_group_rules.side_effect = ClientError(
        {"Error": {"Code": "UnauthorizedAccess", "Message": "denied"}},
        "DescribeSecurityGroupRules",
    )
    with pytest.raises(ClientError):
        _ = sgr.exists


def test_delete_ingress_rule(sgr: SecurityGroupRule, mock_ec2_client: MagicMock) -> None:
    """Ingress rule should be revoked with revoke_security_group_ingress."""
    mock_ec2_client.describe_security_group_rules.return_value = {
        "SecurityGroupRules": [{"SecurityGroupRuleId": "sgr-0abcdef1234567890", "GroupId": "sg-123", "IsEgress": False}]
    }
    sgr.delete()
    mock_ec2_client.revoke_security_group_ingress.assert_called_once_with(
        GroupId="sg-123",
        SecurityGroupRuleIds=["sgr-0abcdef1234567890"],
    )
    mock_ec2_client.revoke_security_group_egress.assert_not_called()


def test_delete_egress_rule(sgr: SecurityGroupRule, mock_ec2_client: MagicMock) -> None:
    """Egress rule should be revoked with revoke_security_group_egress."""
    mock_ec2_client.describe_security_group_rules.return_value = {
        "SecurityGroupRules": [{"SecurityGroupRuleId": "sgr-0abcdef1234567890", "GroupId": "sg-123", "IsEgress": True}]
    }
    sgr.delete()
    mock_ec2_client.revoke_security_group_egress.assert_called_once_with(
        GroupId="sg-123",
        SecurityGroupRuleIds=["sgr-0abcdef1234567890"],
    )
    mock_ec2_client.revoke_security_group_ingress.assert_not_called()


def test_delete_already_gone(sgr: SecurityGroupRule, mock_ec2_client: MagicMock) -> None:
    """Deleting an already-gone rule should be a no-op."""
    mock_ec2_client.describe_security_group_rules.side_effect = ClientError(
        {"Error": {"Code": "InvalidSecurityGroupRuleId.NotFound", "Message": "not found"}},
        "DescribeSecurityGroupRules",
    )
    sgr.delete()
    mock_ec2_client.revoke_security_group_ingress.assert_not_called()
    mock_ec2_client.revoke_security_group_egress.assert_not_called()
