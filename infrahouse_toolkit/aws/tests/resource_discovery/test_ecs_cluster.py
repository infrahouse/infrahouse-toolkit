"""Tests for :class:`infrahouse_toolkit.aws.resource_discovery.ECSCluster`."""

from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from infrahouse_toolkit.aws.resource_discovery import ECSCluster


@pytest.fixture()
def mock_ecs_client() -> MagicMock:
    """Return a mock ECS client."""
    return MagicMock()


@pytest.fixture()
def cluster(mock_ecs_client: MagicMock) -> ECSCluster:
    """Return an ECSCluster with a mocked ECS client."""
    c = ECSCluster(cluster_name="my-cluster", region="us-east-1")
    c._client_instance = mock_ecs_client
    return c


def test_exists_active(cluster: ECSCluster, mock_ecs_client: MagicMock) -> None:
    """Active cluster should return True."""
    mock_ecs_client.describe_clusters.return_value = {"clusters": [{"clusterName": "my-cluster", "status": "ACTIVE"}]}
    assert cluster.exists is True


def test_exists_inactive(cluster: ECSCluster, mock_ecs_client: MagicMock) -> None:
    """Inactive cluster should return False."""
    mock_ecs_client.describe_clusters.return_value = {"clusters": [{"clusterName": "my-cluster", "status": "INACTIVE"}]}
    assert cluster.exists is False


def test_exists_not_found(cluster: ECSCluster, mock_ecs_client: MagicMock) -> None:
    """Empty clusters list should return False."""
    mock_ecs_client.describe_clusters.return_value = {"clusters": []}
    assert cluster.exists is False


def test_exists_client_error(cluster: ECSCluster, mock_ecs_client: MagicMock) -> None:
    """ClientError should return False."""
    mock_ecs_client.describe_clusters.side_effect = ClientError(
        {"Error": {"Code": "ClusterNotFoundException", "Message": "not found"}},
        "DescribeClusters",
    )
    assert cluster.exists is False


def test_delete(cluster: ECSCluster, mock_ecs_client: MagicMock) -> None:
    """Delete should call delete_cluster."""
    cluster.delete()
    mock_ecs_client.delete_cluster.assert_called_once_with(cluster="my-cluster")
