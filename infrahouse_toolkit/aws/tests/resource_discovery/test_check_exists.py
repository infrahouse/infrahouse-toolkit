"""Tests for :func:`infrahouse_toolkit.aws.resource_discovery._check_exists`."""

from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from botocore.exceptions import ClientError

from infrahouse_toolkit.aws.resource_discovery import _check_exists


def test_check_exists_returns_false_on_index_error() -> None:
    """When infrahouse-core raises IndexError (empty describe_instances response), treat as deleted."""
    arn = "arn:aws:ec2:us-east-1:123456789012:instance/i-0abcdef1234567890"
    mock_resource = MagicMock()
    type(mock_resource).exists = PropertyMock(side_effect=IndexError("list index out of range"))

    with patch("infrahouse_toolkit.aws.resource_discovery.resource_for_arn", return_value=mock_resource):
        assert _check_exists(arn) is False


def test_check_exists_returns_true_on_client_error() -> None:
    """ClientError should be treated as 'assume exists'."""
    arn = "arn:aws:ec2:us-east-1:123456789012:instance/i-0abcdef1234567890"
    mock_resource = MagicMock()
    error_response = {"Error": {"Code": "UnauthorizedAccess", "Message": "Access denied"}}
    type(mock_resource).exists = PropertyMock(side_effect=ClientError(error_response, "DescribeInstances"))

    with patch("infrahouse_toolkit.aws.resource_discovery.resource_for_arn", return_value=mock_resource):
        assert _check_exists(arn) is True


def test_check_exists_returns_true_for_unsupported_arn() -> None:
    """Unsupported ARNs (resource_for_arn returns None) should assume exists."""
    arn = "arn:aws:redshift:us-east-1:123456789012:cluster:my-cluster"
    assert _check_exists(arn) is True


def test_check_exists_returns_true_when_resource_exists() -> None:
    """Happy path: resource.exists returns True."""
    arn = "arn:aws:ec2:us-east-1:123456789012:instance/i-0abcdef1234567890"
    mock_resource = MagicMock()
    type(mock_resource).exists = PropertyMock(return_value=True)

    with patch("infrahouse_toolkit.aws.resource_discovery.resource_for_arn", return_value=mock_resource):
        assert _check_exists(arn) is True


def test_check_exists_returns_false_when_resource_terminated() -> None:
    """Resource.exists returns False (e.g. terminated instance)."""
    arn = "arn:aws:ec2:us-east-1:123456789012:instance/i-0abcdef1234567890"
    mock_resource = MagicMock()
    type(mock_resource).exists = PropertyMock(return_value=False)

    with patch("infrahouse_toolkit.aws.resource_discovery.resource_for_arn", return_value=mock_resource):
        assert _check_exists(arn) is False
