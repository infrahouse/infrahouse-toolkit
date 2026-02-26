"""Tests for :class:`infrahouse_toolkit.aws.resource_discovery.ECSService`."""

from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from infrahouse_toolkit.aws.resource_discovery import ECSService


@pytest.fixture()
def mock_ecs_client() -> MagicMock:
    """Return a mock ECS client."""
    return MagicMock()


@pytest.fixture()
def svc(mock_ecs_client: MagicMock) -> ECSService:
    """Return an ECSService with a mocked ECS client."""
    s = ECSService(cluster="my-cluster", service_name="my-service", region="us-east-1")
    s._client_instance = mock_ecs_client
    return s


def test_exists_active(svc: ECSService, mock_ecs_client: MagicMock) -> None:
    """Active service should return True."""
    mock_ecs_client.describe_services.return_value = {"services": [{"serviceName": "my-service", "status": "ACTIVE"}]}
    assert svc.exists is True


def test_exists_draining(svc: ECSService, mock_ecs_client: MagicMock) -> None:
    """Draining service should return True."""
    mock_ecs_client.describe_services.return_value = {"services": [{"serviceName": "my-service", "status": "DRAINING"}]}
    assert svc.exists is True


def test_exists_inactive(svc: ECSService, mock_ecs_client: MagicMock) -> None:
    """Inactive service should return False."""
    mock_ecs_client.describe_services.return_value = {"services": [{"serviceName": "my-service", "status": "INACTIVE"}]}
    assert svc.exists is False


def test_exists_not_found(svc: ECSService, mock_ecs_client: MagicMock) -> None:
    """Empty services list should return False."""
    mock_ecs_client.describe_services.return_value = {"services": []}
    assert svc.exists is False


def test_exists_client_error(svc: ECSService, mock_ecs_client: MagicMock) -> None:
    """ClientError should return False."""
    mock_ecs_client.describe_services.side_effect = ClientError(
        {"Error": {"Code": "ClusterNotFoundException", "Message": "not found"}},
        "DescribeServices",
    )
    assert svc.exists is False


def test_delete(svc: ECSService, mock_ecs_client: MagicMock) -> None:
    """Delete should scale to zero then force-delete."""
    svc.delete()
    mock_ecs_client.update_service.assert_called_once_with(
        cluster="my-cluster",
        service="my-service",
        desiredCount=0,
    )
    mock_ecs_client.delete_service.assert_called_once_with(
        cluster="my-cluster",
        service="my-service",
        force=True,
    )


def test_delete_update_fails(svc: ECSService, mock_ecs_client: MagicMock) -> None:
    """Delete should proceed even if update_service fails."""
    mock_ecs_client.update_service.side_effect = ClientError(
        {"Error": {"Code": "ServiceNotActiveException", "Message": "not active"}},
        "UpdateService",
    )
    svc.delete()
    mock_ecs_client.delete_service.assert_called_once_with(
        cluster="my-cluster",
        service="my-service",
        force=True,
    )
