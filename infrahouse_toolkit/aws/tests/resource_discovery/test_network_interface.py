"""Tests for :class:`infrahouse_toolkit.aws.resource_discovery.NetworkInterface`."""

from unittest.mock import MagicMock, call, patch

import pytest
from botocore.exceptions import ClientError

from infrahouse_toolkit.aws.resource_discovery import NetworkInterface


@pytest.fixture()
def mock_ec2_client() -> MagicMock:
    """Return a mock EC2 client."""
    return MagicMock()


@pytest.fixture()
def eni(mock_ec2_client: MagicMock) -> NetworkInterface:
    """Return a NetworkInterface with a mocked EC2 client."""
    ni = NetworkInterface("eni-0abcdef1234567890", region="us-east-1")
    ni._client_instance = mock_ec2_client
    return ni


def test_exists_returns_true_when_present(eni: NetworkInterface, mock_ec2_client: MagicMock) -> None:
    """ENI that exists in AWS should return True."""
    mock_ec2_client.describe_network_interfaces.return_value = {
        "NetworkInterfaces": [{"NetworkInterfaceId": "eni-0abcdef1234567890", "Status": "available"}]
    }
    assert eni.exists is True


def test_exists_returns_false_when_not_found(eni: NetworkInterface, mock_ec2_client: MagicMock) -> None:
    """ENI not found should return False."""
    mock_ec2_client.describe_network_interfaces.side_effect = ClientError(
        {"Error": {"Code": "InvalidNetworkInterfaceID.NotFound", "Message": "not found"}},
        "DescribeNetworkInterfaces",
    )
    assert eni.exists is False


def test_exists_raises_on_unexpected_error(eni: NetworkInterface, mock_ec2_client: MagicMock) -> None:
    """Unexpected ClientError should propagate."""
    mock_ec2_client.describe_network_interfaces.side_effect = ClientError(
        {"Error": {"Code": "UnauthorizedAccess", "Message": "denied"}},
        "DescribeNetworkInterfaces",
    )
    with pytest.raises(ClientError):
        _ = eni.exists


def test_delete_available_eni(eni: NetworkInterface, mock_ec2_client: MagicMock) -> None:
    """Available (detached) ENI should be deleted directly."""
    mock_ec2_client.describe_network_interfaces.return_value = {
        "NetworkInterfaces": [{"NetworkInterfaceId": "eni-0abcdef1234567890", "Status": "available"}]
    }
    eni.delete()
    mock_ec2_client.detach_network_interface.assert_not_called()
    mock_ec2_client.delete_network_interface.assert_called_once_with(NetworkInterfaceId="eni-0abcdef1234567890")


def test_delete_attached_eni(eni: NetworkInterface, mock_ec2_client: MagicMock) -> None:
    """Attached ENI should be force-detached then deleted."""
    mock_ec2_client.describe_network_interfaces.return_value = {
        "NetworkInterfaces": [
            {
                "NetworkInterfaceId": "eni-0abcdef1234567890",
                "Status": "in-use",
                "Attachment": {"AttachmentId": "eni-attach-12345"},
            }
        ]
    }
    mock_waiter = MagicMock()
    mock_ec2_client.get_waiter.return_value = mock_waiter

    eni.delete()

    mock_ec2_client.detach_network_interface.assert_called_once_with(
        AttachmentId="eni-attach-12345",
        Force=True,
    )
    mock_waiter.wait.assert_called_once_with(NetworkInterfaceIds=["eni-0abcdef1234567890"])
    mock_ec2_client.delete_network_interface.assert_called_once_with(NetworkInterfaceId="eni-0abcdef1234567890")


def test_delete_already_gone(eni: NetworkInterface, mock_ec2_client: MagicMock) -> None:
    """Deleting an already-gone ENI should be a no-op."""
    mock_ec2_client.describe_network_interfaces.side_effect = ClientError(
        {"Error": {"Code": "InvalidNetworkInterfaceID.NotFound", "Message": "not found"}},
        "DescribeNetworkInterfaces",
    )
    eni.delete()
    mock_ec2_client.delete_network_interface.assert_not_called()
