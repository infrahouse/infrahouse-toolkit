"""Tests for :class:`infrahouse_toolkit.aws.resource_discovery.EBSVolume`."""

from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from infrahouse_toolkit.aws.resource_discovery import EBSVolume


@pytest.fixture()
def mock_ec2_client() -> MagicMock:
    """Return a mock EC2 client."""
    return MagicMock()


@pytest.fixture()
def vol(mock_ec2_client: MagicMock) -> EBSVolume:
    """Return an EBSVolume with a mocked EC2 client."""
    v = EBSVolume("vol-0abcdef1234567890", region="us-east-1")
    v._client_instance = mock_ec2_client
    return v


def test_exists_available(vol: EBSVolume, mock_ec2_client: MagicMock) -> None:
    """Available volume should return True."""
    mock_ec2_client.describe_volumes.return_value = {
        "Volumes": [{"VolumeId": "vol-0abcdef1234567890", "State": "available"}]
    }
    assert vol.exists is True


def test_exists_in_use(vol: EBSVolume, mock_ec2_client: MagicMock) -> None:
    """In-use volume should return True."""
    mock_ec2_client.describe_volumes.return_value = {
        "Volumes": [{"VolumeId": "vol-0abcdef1234567890", "State": "in-use"}]
    }
    assert vol.exists is True


def test_exists_not_found(vol: EBSVolume, mock_ec2_client: MagicMock) -> None:
    """Volume not found should return False."""
    mock_ec2_client.describe_volumes.side_effect = ClientError(
        {"Error": {"Code": "InvalidVolume.NotFound", "Message": "not found"}},
        "DescribeVolumes",
    )
    assert vol.exists is False


def test_exists_raises_on_unexpected_error(vol: EBSVolume, mock_ec2_client: MagicMock) -> None:
    """Unexpected ClientError should propagate."""
    mock_ec2_client.describe_volumes.side_effect = ClientError(
        {"Error": {"Code": "UnauthorizedAccess", "Message": "denied"}},
        "DescribeVolumes",
    )
    with pytest.raises(ClientError):
        _ = vol.exists


def test_delete_available_volume(vol: EBSVolume, mock_ec2_client: MagicMock) -> None:
    """Available volume should be deleted directly."""
    mock_ec2_client.describe_volumes.return_value = {
        "Volumes": [{"VolumeId": "vol-0abcdef1234567890", "State": "available", "Attachments": []}]
    }
    vol.delete()
    mock_ec2_client.detach_volume.assert_not_called()
    mock_ec2_client.delete_volume.assert_called_once_with(VolumeId="vol-0abcdef1234567890")


def test_delete_attached_volume(vol: EBSVolume, mock_ec2_client: MagicMock) -> None:
    """Attached volume should be force-detached then deleted."""
    mock_ec2_client.describe_volumes.return_value = {
        "Volumes": [
            {
                "VolumeId": "vol-0abcdef1234567890",
                "State": "in-use",
                "Attachments": [{"InstanceId": "i-123", "VolumeId": "vol-0abcdef1234567890"}],
            }
        ]
    }
    mock_waiter = MagicMock()
    mock_ec2_client.get_waiter.return_value = mock_waiter

    vol.delete()

    mock_ec2_client.detach_volume.assert_called_once_with(
        VolumeId="vol-0abcdef1234567890",
        InstanceId="i-123",
        Force=True,
    )
    mock_waiter.wait.assert_called_once_with(VolumeIds=["vol-0abcdef1234567890"])
    mock_ec2_client.delete_volume.assert_called_once_with(VolumeId="vol-0abcdef1234567890")


def test_delete_already_gone(vol: EBSVolume, mock_ec2_client: MagicMock) -> None:
    """Deleting an already-gone volume should be a no-op."""
    mock_ec2_client.describe_volumes.side_effect = ClientError(
        {"Error": {"Code": "InvalidVolume.NotFound", "Message": "not found"}},
        "DescribeVolumes",
    )
    vol.delete()
    mock_ec2_client.delete_volume.assert_not_called()
