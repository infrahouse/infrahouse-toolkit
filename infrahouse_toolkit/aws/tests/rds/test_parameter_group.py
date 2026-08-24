"""Tests for :class:`infrahouse_toolkit.aws.rds.RDSParameterGroup`."""

from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from infrahouse_toolkit.aws.rds import RDSParameterError, RDSParameterGroup

PARAMETERS = {
    "log_output": {
        "ParameterName": "log_output",
        "ParameterValue": "TABLE",
        "Source": "system",
        "ApplyType": "dynamic",
        "IsModifiable": True,
    },
    "long_query_time": {
        "ParameterName": "long_query_time",
        "Source": "engine-default",
        "ApplyType": "dynamic",
        "IsModifiable": True,
    },
    "slow_query_log": {
        "ParameterName": "slow_query_log",
        "ParameterValue": "1",
        "Source": "user",
        "ApplyType": "dynamic",
        "IsModifiable": True,
    },
    "slow_query_log_file": {
        "ParameterName": "slow_query_log_file",
        "ParameterValue": "/rdsdbdata/log/slowquery/mysql-slowquery.log",
        "Source": "system",
        "ApplyType": "dynamic",
        "IsModifiable": False,
    },
    "performance_schema": {
        "ParameterName": "performance_schema",
        "ParameterValue": "0",
        "Source": "system",
        "ApplyType": "static",
        "IsModifiable": True,
    },
}


@pytest.fixture()
def rds_client() -> MagicMock:
    """Return a mock RDS client serving one mysql8.0 parameter group."""
    client = MagicMock()
    client.describe_db_parameter_groups.return_value = {
        "DBParameterGroups": [{"DBParameterGroupName": "test-pg", "DBParameterGroupFamily": "mysql8.0"}]
    }

    def paginator_for(name):
        paginator = MagicMock()
        if name == "describe_db_parameters":
            paginator.paginate.return_value = [{"Parameters": list(PARAMETERS.values())}]
        else:
            paginator.paginate.return_value = [
                {
                    "DBInstances": [
                        {
                            "DBInstanceIdentifier": "test-instance",
                            "DBParameterGroups": [{"DBParameterGroupName": "test-pg"}],
                        },
                        {
                            "DBInstanceIdentifier": "other-instance",
                            "DBParameterGroups": [{"DBParameterGroupName": "other-pg"}],
                        },
                    ]
                }
            ]
        return paginator

    client.get_paginator.side_effect = paginator_for
    return client


@pytest.fixture()
def group(rds_client: MagicMock) -> RDSParameterGroup:
    """Return an RDSParameterGroup backed by the mock client."""
    session = MagicMock()
    session.client.return_value = rds_client
    return RDSParameterGroup("test-pg", session=session)


def test_family(group: RDSParameterGroup) -> None:
    """family comes from describe_db_parameter_groups."""
    assert group.family == "mysql8.0"


def test_attached_instance_ids(group: RDSParameterGroup) -> None:
    """Only instances actually using the group are reported."""
    assert group.attached_instance_ids == ["test-instance"]


def test_is_default() -> None:
    """RDS-provided groups are recognised by their name prefix."""
    assert RDSParameterGroup("default.mysql8.0", session=MagicMock()).is_default is True
    assert RDSParameterGroup("test-pg", session=MagicMock()).is_default is False


def test_value_of_unset_parameter(group: RDSParameterGroup) -> None:
    """A parameter inheriting the engine default has no value."""
    assert group.value_of("long_query_time") is None
    assert group.value_of("log_output") == "TABLE"


def test_apply_sets_parameters_immediately(group: RDSParameterGroup, rds_client: MagicMock) -> None:
    """apply() writes every value with ApplyMethod=immediate."""
    group.apply({"log_output": "FILE", "long_query_time": "0"})
    kwargs = rds_client.modify_db_parameter_group.call_args.kwargs
    assert kwargs["DBParameterGroupName"] == "test-pg"
    assert kwargs["Parameters"] == [
        {"ParameterName": "log_output", "ParameterValue": "FILE", "ApplyMethod": "immediate"},
        {"ParameterName": "long_query_time", "ParameterValue": "0", "ApplyMethod": "immediate"},
    ]


def test_apply_rejects_default_group() -> None:
    """A default parameter group cannot be modified at all."""
    group = RDSParameterGroup("default.mysql8.0", session=MagicMock())
    with pytest.raises(RDSParameterError) as exc_info:
        group.apply({"log_output": "FILE"})
    assert "default parameter group" in str(exc_info.value)


def test_validate_modifiable_rejects_read_only(group: RDSParameterGroup) -> None:
    """slow_query_log_file is fixed on RDS and must be refused."""
    with pytest.raises(RDSParameterError) as exc_info:
        group.validate_modifiable(["slow_query_log_file"])
    assert "not modifiable" in str(exc_info.value)


def test_validate_modifiable_rejects_static(group: RDSParameterGroup) -> None:
    """A static parameter would need a reboot, so it is refused up front."""
    with pytest.raises(RDSParameterError) as exc_info:
        group.validate_modifiable(["performance_schema"])
    assert "not dynamic" in str(exc_info.value)


def test_validate_modifiable_rejects_unknown(group: RDSParameterGroup) -> None:
    """A parameter absent from the family (e.g. a Percona-only one) is refused."""
    with pytest.raises(RDSParameterError) as exc_info:
        group.validate_modifiable(["log_slow_verbosity"])
    assert "does not exist in family mysql8.0" in str(exc_info.value)


def test_snapshot_records_value_and_source(group: RDSParameterGroup) -> None:
    """snapshot() keeps the origin, not just the value."""
    assert group.snapshot(["slow_query_log", "long_query_time"]) == [
        {"name": "slow_query_log", "value": "1", "source": "user"},
        {"name": "long_query_time", "value": None, "source": "engine-default"},
    ]


def test_snapshot_rejects_unknown_parameter(group: RDSParameterGroup) -> None:
    """Recording a parameter that does not exist is an error, not a None entry."""
    with pytest.raises(RDSParameterError):
        group.snapshot(["use_global_long_query_time"])


def test_restore_sets_user_values_and_resets_defaults(group: RDSParameterGroup, rds_client: MagicMock) -> None:
    """User-set parameters are written back; inherited ones are reset, not pinned."""
    group.restore(
        [
            {"name": "slow_query_log", "value": "1", "source": "user"},
            {"name": "long_query_time", "value": None, "source": "engine-default"},
            {"name": "log_output", "value": "TABLE", "source": "system"},
        ]
    )
    assert rds_client.modify_db_parameter_group.call_args.kwargs["Parameters"] == [
        {"ParameterName": "slow_query_log", "ParameterValue": "1", "ApplyMethod": "immediate"}
    ]
    assert rds_client.reset_db_parameter_group.call_args.kwargs["Parameters"] == [
        {"ParameterName": "long_query_time", "ApplyMethod": "immediate"},
        {"ParameterName": "log_output", "ApplyMethod": "immediate"},
    ]


def test_restore_without_user_values_only_resets(group: RDSParameterGroup, rds_client: MagicMock) -> None:
    """Nothing is written when every parameter was inherited."""
    group.restore([{"name": "long_query_time", "value": None, "source": "engine-default"}])
    rds_client.modify_db_parameter_group.assert_not_called()
    rds_client.reset_db_parameter_group.assert_called_once()


def test_exists(group: RDSParameterGroup) -> None:
    """The AWSResource contract: the group is there."""
    assert group.exists is True


def test_does_not_exist(group: RDSParameterGroup, rds_client: MagicMock) -> None:
    """A missing group is False, not an exception."""
    rds_client.describe_db_parameter_groups.side_effect = ClientError(
        {"Error": {"Code": "DBParameterGroupNotFound", "Message": "nope"}}, "DescribeDBParameterGroups"
    )
    assert group.exists is False


def test_exists_propagates_other_errors(group: RDSParameterGroup, rds_client: MagicMock) -> None:
    """A permissions problem must not read as "does not exist"."""
    rds_client.describe_db_parameter_groups.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "denied"}}, "DescribeDBParameterGroups"
    )
    with pytest.raises(ClientError):
        _ = group.exists


def test_delete_is_idempotent(group: RDSParameterGroup, rds_client: MagicMock) -> None:
    """Deleting a group that is already gone is a no-op."""
    rds_client.delete_db_parameter_group.side_effect = ClientError(
        {"Error": {"Code": "DBParameterGroupNotFound", "Message": "nope"}}, "DeleteDBParameterGroup"
    )
    group.delete()
