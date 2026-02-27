"""Tests for :class:`infrahouse_toolkit.aws.resource_discovery.KeyPair`."""

from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from infrahouse_toolkit.aws.resource_discovery import KeyPair


@pytest.fixture()
def mock_ec2_client() -> MagicMock:
    """Return a mock EC2 client."""
    return MagicMock()


@pytest.fixture()
def kp(mock_ec2_client: MagicMock) -> KeyPair:
    """Return a KeyPair with a mocked EC2 client."""
    k = KeyPair("key-0abcdef1234567890", region="us-east-1")
    k._client_instance = mock_ec2_client
    return k


def test_exists_returns_true(kp: KeyPair, mock_ec2_client: MagicMock) -> None:
    """Key pair that exists should return True."""
    mock_ec2_client.describe_key_pairs.return_value = {"KeyPairs": [{"KeyPairId": "key-0abcdef1234567890"}]}
    assert kp.exists is True


def test_exists_returns_false(kp: KeyPair, mock_ec2_client: MagicMock) -> None:
    """Key pair not found should return False."""
    mock_ec2_client.describe_key_pairs.side_effect = ClientError(
        {"Error": {"Code": "InvalidKeyPair.NotFound", "Message": "not found"}},
        "DescribeKeyPairs",
    )
    assert kp.exists is False


def test_exists_raises_on_unexpected_error(kp: KeyPair, mock_ec2_client: MagicMock) -> None:
    """Unexpected ClientError should propagate."""
    mock_ec2_client.describe_key_pairs.side_effect = ClientError(
        {"Error": {"Code": "UnauthorizedAccess", "Message": "denied"}},
        "DescribeKeyPairs",
    )
    with pytest.raises(ClientError):
        _ = kp.exists


def test_delete(kp: KeyPair, mock_ec2_client: MagicMock) -> None:
    """Delete should call delete_key_pair."""
    kp.delete()
    mock_ec2_client.delete_key_pair.assert_called_once_with(KeyPairId="key-0abcdef1234567890")
