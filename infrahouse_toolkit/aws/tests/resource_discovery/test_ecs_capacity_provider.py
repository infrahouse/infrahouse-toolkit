"""Tests for :class:`infrahouse_toolkit.aws.resource_discovery.ECSCapacityProvider`."""

from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from infrahouse_toolkit.aws.resource_discovery import ECSCapacityProvider


@pytest.fixture()
def mock_ecs_client() -> MagicMock:
    """Return a mock ECS client."""
    return MagicMock()


@pytest.fixture()
def cp(mock_ecs_client: MagicMock) -> ECSCapacityProvider:
    """Return an ECSCapacityProvider with a mocked ECS client."""
    c = ECSCapacityProvider(name="my-cp", region="us-east-1")
    c._client_instance = mock_ecs_client
    return c


def test_exists_active(cp: ECSCapacityProvider, mock_ecs_client: MagicMock) -> None:
    """Active capacity provider should return True."""
    mock_ecs_client.describe_capacity_providers.return_value = {
        "capacityProviders": [{"name": "my-cp", "status": "ACTIVE"}]
    }
    assert cp.exists is True


def test_exists_inactive(cp: ECSCapacityProvider, mock_ecs_client: MagicMock) -> None:
    """Inactive capacity provider should return False."""
    mock_ecs_client.describe_capacity_providers.return_value = {
        "capacityProviders": [{"name": "my-cp", "status": "INACTIVE"}]
    }
    assert cp.exists is False


def test_exists_not_found(cp: ECSCapacityProvider, mock_ecs_client: MagicMock) -> None:
    """Empty list should return False."""
    mock_ecs_client.describe_capacity_providers.return_value = {"capacityProviders": []}
    assert cp.exists is False


def test_exists_client_error(cp: ECSCapacityProvider, mock_ecs_client: MagicMock) -> None:
    """ClientError should return False."""
    mock_ecs_client.describe_capacity_providers.side_effect = ClientError(
        {"Error": {"Code": "ServerException", "Message": "error"}},
        "DescribeCapacityProviders",
    )
    assert cp.exists is False


def test_delete(cp: ECSCapacityProvider, mock_ecs_client: MagicMock) -> None:
    """Delete should call delete_capacity_provider."""
    cp.delete()
    mock_ecs_client.delete_capacity_provider.assert_called_once_with(capacityProvider="my-cp")
