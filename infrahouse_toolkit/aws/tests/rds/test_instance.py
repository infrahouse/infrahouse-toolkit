"""Tests for :class:`infrahouse_toolkit.aws.rds.RDSMySQLInstance`."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
import requests
from botocore.credentials import Credentials
from botocore.exceptions import ClientError

from infrahouse_toolkit.aws.rds import RDSError, RDSInstanceNotFound, RDSMySQLInstance

DESCRIPTION = {
    "DBInstanceIdentifier": "test-instance",
    "DBInstanceStatus": "available",
    "Engine": "mysql",
    "EngineVersion": "8.0.45",
    "AllocatedStorage": 200,
    "EnabledCloudwatchLogsExports": ["error", "general", "slowquery"],
    "PerformanceInsightsEnabled": True,
    "DBParameterGroups": [{"DBParameterGroupName": "test-pg", "ParameterApplyStatus": "in-sync"}],
}


@pytest.fixture()
def session() -> MagicMock:
    """Return a mock boto3 session whose RDS client describes one instance."""
    rds = MagicMock()
    rds.meta.region_name = "us-west-1"
    rds.describe_db_instances.return_value = {"DBInstances": [DESCRIPTION]}
    mock = MagicMock()
    mock.region_name = "us-west-1"
    mock.client.return_value = rds
    mock.get_credentials.return_value = Credentials("AKIAEXAMPLE", "secret", "token")
    return mock


@pytest.fixture()
def instance(session: MagicMock) -> RDSMySQLInstance:
    """Return an RDSInstance backed by the mock session."""
    return RDSMySQLInstance("test-instance", session=session)


def test_basic_properties(instance: RDSMySQLInstance) -> None:
    """Scalar properties come straight from describe_db_instances."""
    assert instance.engine == "mysql"
    assert instance.engine_version == "8.0.45"
    assert instance.status == "available"
    assert instance.allocated_storage_bytes == 200 * 1024**3
    assert instance.cloudwatch_log_exports == ["error", "general", "slowquery"]
    assert instance.performance_insights_enabled is True
    assert instance.parameter_apply_status == "in-sync"
    assert instance.parameter_group.name == "test-pg"


def test_missing_instance(session: MagicMock) -> None:
    """A nonexistent instance raises a typed error, not a raw ClientError."""
    session.client.return_value.describe_db_instances.side_effect = ClientError(
        {"Error": {"Code": "DBInstanceNotFound", "Message": "not found"}}, "DescribeDBInstances"
    )
    with pytest.raises(RDSInstanceNotFound):
        _ = RDSMySQLInstance("nope", session=session).engine


def test_other_client_errors_propagate(session: MagicMock) -> None:
    """Errors that are not "missing instance" are not swallowed."""
    session.client.return_value.describe_db_instances.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "denied"}}, "DescribeDBInstances"
    )
    with pytest.raises(ClientError):
        _ = RDSMySQLInstance("test-instance", session=session).engine


def test_slow_log_files_sorted_oldest_first(instance: RDSMySQLInstance, session: MagicMock) -> None:
    """Log files come back ordered by write time."""
    paginator = MagicMock()
    paginator.paginate.return_value = [
        {
            "DescribeDBLogFiles": [
                {"LogFileName": "slowquery/mysql-slowquery.log", "Size": 300, "LastWritten": 3},
                {"LogFileName": "slowquery/mysql-slowquery.log.2026-08-24.9", "Size": 100, "LastWritten": 1},
            ]
        }
    ]
    session.client.return_value.get_paginator.return_value = paginator

    assert [entry["name"] for entry in instance.slow_log_files] == [
        "slowquery/mysql-slowquery.log.2026-08-24.9",
        "slowquery/mysql-slowquery.log",
    ]
    assert instance.slow_log_size == 400


def test_slow_log_files_when_log_output_is_table(instance: RDSMySQLInstance, session: MagicMock) -> None:
    """With log_output=TABLE there are no files at all — the common RDS default."""
    paginator = MagicMock()
    paginator.paginate.return_value = [{"DescribeDBLogFiles": []}]
    session.client.return_value.get_paginator.return_value = paginator
    assert instance.slow_log_files == []
    assert instance.slow_log_size == 0


def test_free_storage_bytes_uses_latest_datapoint(instance: RDSMySQLInstance, session: MagicMock) -> None:
    """The most recent CloudWatch reading wins."""
    cloudwatch = MagicMock()
    cloudwatch.get_metric_statistics.return_value = {
        "Datapoints": [
            {"Timestamp": datetime(2026, 8, 24, 10, tzinfo=timezone.utc), "Minimum": 100.0},
            {"Timestamp": datetime(2026, 8, 24, 11, tzinfo=timezone.utc), "Minimum": 90.0},
        ]
    }
    session.client.side_effect = lambda name, **kwargs: cloudwatch if name == "cloudwatch" else MagicMock()
    assert RDSMySQLInstance("test-instance", session=session).free_storage_bytes == 90


def test_free_storage_bytes_without_datapoints(session: MagicMock) -> None:
    """CloudWatch lag yields None rather than a made-up number."""
    cloudwatch = MagicMock()
    cloudwatch.get_metric_statistics.return_value = {"Datapoints": []}
    session.client.side_effect = lambda name, **kwargs: cloudwatch if name == "cloudwatch" else MagicMock()
    assert RDSMySQLInstance("test-instance", session=session).free_storage_bytes is None


def test_wait_parameters_in_sync_returns_when_synced(instance: RDSMySQLInstance) -> None:
    """Nothing to wait for once the group reports in-sync."""
    with patch("infrahouse_toolkit.aws.rds.instance.time.sleep"):
        instance.wait_parameters_in_sync(settle=0)


def test_wait_parameters_in_sync_raises_on_failure(instance: RDSMySQLInstance, session: MagicMock) -> None:
    """A failed apply is an error, not something to keep polling."""
    session.client.return_value.describe_db_instances.return_value = {
        "DBInstances": [
            dict(
                DESCRIPTION,
                DBParameterGroups=[{"DBParameterGroupName": "test-pg", "ParameterApplyStatus": "failed-to-apply"}],
            )
        ]
    }
    with patch("infrahouse_toolkit.aws.rds.instance.time.sleep"):
        with pytest.raises(RDSError) as exc_info:
            instance.wait_parameters_in_sync(settle=0)
    assert "failed to apply" in str(exc_info.value)


def test_wait_parameters_in_sync_times_out(instance: RDSMySQLInstance, session: MagicMock) -> None:
    """A group stuck in applying eventually gives up."""
    session.client.return_value.describe_db_instances.return_value = {
        "DBInstances": [
            dict(
                DESCRIPTION,
                DBParameterGroups=[{"DBParameterGroupName": "test-pg", "ParameterApplyStatus": "applying"}],
            )
        ]
    }
    with patch("infrahouse_toolkit.aws.rds.instance.time.sleep"):
        with pytest.raises(RDSError) as exc_info:
            instance.wait_parameters_in_sync(timeout=0, settle=0)
    assert "did not reach in-sync" in str(exc_info.value)


def test_download_falls_back_to_portion_api(instance: RDSMySQLInstance, session: MagicMock, tmp_path) -> None:
    """When the streaming endpoint fails, the paginated API finishes the job."""
    rds = session.client.return_value
    rds.download_db_log_file_portion.side_effect = [
        {"LogFileData": "first\n", "Marker": "1", "AdditionalDataPending": True},
        {"LogFileData": "second\n", "Marker": "2", "AdditionalDataPending": False},
    ]
    with patch(
        "infrahouse_toolkit.aws.rds.instance.requests.get",
        side_effect=requests.RequestException("nope"),
    ):
        path = instance.download_log_file("slowquery/mysql-slowquery.log", str(tmp_path))

    assert open(path, encoding="utf8").read() == "first\nsecond\n"
    assert rds.download_db_log_file_portion.call_count == 2


def test_download_streams_complete_log_file(instance: RDSMySQLInstance, tmp_path) -> None:
    """The signed REST endpoint is tried first and streams the whole file."""
    response = MagicMock()
    response.__enter__.return_value = response
    response.iter_content.return_value = [b"slow log ", b"contents"]

    with patch("infrahouse_toolkit.aws.rds.instance.requests.get", return_value=response) as mock_get:
        path = instance.download_log_file("slowquery/mysql-slowquery.log", str(tmp_path))

    url = mock_get.call_args.args[0]
    assert url == (
        "https://rds.us-west-1.amazonaws.com/v13/downloadCompleteLogFile/test-instance/" "slowquery/mysql-slowquery.log"
    )
    assert "Authorization" in mock_get.call_args.kwargs["headers"]
    assert open(path, "rb").read() == b"slow log contents"


def test_download_names_file_without_slashes(instance: RDSMySQLInstance, tmp_path) -> None:
    """The RDS log name contains a directory part that must not become one locally."""
    response = MagicMock()
    response.__enter__.return_value = response
    response.iter_content.return_value = [b""]
    with patch("infrahouse_toolkit.aws.rds.instance.requests.get", return_value=response):
        path = instance.download_log_file("slowquery/mysql-slowquery.log", str(tmp_path))
    assert path.endswith("slowquery-mysql-slowquery.log")
