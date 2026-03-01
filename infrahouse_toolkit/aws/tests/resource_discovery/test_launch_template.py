"""Tests for :class:`infrahouse_toolkit.aws.resource_discovery.LaunchTemplate`."""

from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from infrahouse_toolkit.aws.resource_discovery import LaunchTemplate


@pytest.fixture()
def mock_ec2_client() -> MagicMock:
    """Return a mock EC2 client."""
    return MagicMock()


@pytest.fixture()
def lt(mock_ec2_client: MagicMock) -> LaunchTemplate:
    """Return a LaunchTemplate with a mocked EC2 client."""
    t = LaunchTemplate("lt-0abcdef1234567890", region="us-east-1")
    t._client_instance = mock_ec2_client
    return t


def test_exists_returns_true(lt: LaunchTemplate, mock_ec2_client: MagicMock) -> None:
    """Launch template that exists should return True."""
    mock_ec2_client.describe_launch_templates.return_value = {
        "LaunchTemplates": [{"LaunchTemplateId": "lt-0abcdef1234567890"}]
    }
    assert lt.exists is True


def test_exists_returns_false(lt: LaunchTemplate, mock_ec2_client: MagicMock) -> None:
    """Launch template not found should return False."""
    mock_ec2_client.describe_launch_templates.side_effect = ClientError(
        {"Error": {"Code": "InvalidLaunchTemplateId.NotFound", "Message": "not found"}},
        "DescribeLaunchTemplates",
    )
    assert lt.exists is False


def test_exists_raises_on_unexpected_error(lt: LaunchTemplate, mock_ec2_client: MagicMock) -> None:
    """Unexpected ClientError should propagate."""
    mock_ec2_client.describe_launch_templates.side_effect = ClientError(
        {"Error": {"Code": "UnauthorizedAccess", "Message": "denied"}},
        "DescribeLaunchTemplates",
    )
    with pytest.raises(ClientError):
        _ = lt.exists


def test_delete(lt: LaunchTemplate, mock_ec2_client: MagicMock) -> None:
    """Delete should call delete_launch_template."""
    lt.delete()
    mock_ec2_client.delete_launch_template.assert_called_once_with(LaunchTemplateId="lt-0abcdef1234567890")
