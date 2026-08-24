"""Tests for :meth:`infrahouse_toolkit.aws.rds.RDSMySQLInstance.list_instances`."""

from unittest.mock import MagicMock

import pytest

from infrahouse_toolkit.aws.rds import RDSMySQLInstance

PAGE = {
    "DBInstances": [
        {
            "DBInstanceIdentifier": "mysql-two",
            "Engine": "mysql",
            "EngineVersion": "8.0.45",
            "DBInstanceClass": "db.t3.large",
            "DBInstanceStatus": "available",
            "TagList": [{"Key": "service", "Value": "second-service"}],
        },
        {
            "DBInstanceIdentifier": "postgres-one",
            "Engine": "postgres",
            "EngineVersion": "16.3",
            "DBInstanceClass": "db.t3.micro",
            "DBInstanceStatus": "available",
            "TagList": [],
        },
        {
            "DBInstanceIdentifier": "mysql-one",
            "Engine": "mysql",
            "EngineVersion": "8.4.0",
            "DBInstanceClass": "db.t4g.medium",
            "DBInstanceStatus": "available",
            "TagList": [{"Key": "Name", "Value": "first instance"}],
        },
    ]
}


@pytest.fixture()
def session() -> MagicMock:
    """Return a mock session whose RDS paginator yields one page of instances."""
    paginator = MagicMock()
    paginator.paginate.return_value = [PAGE]
    rds = MagicMock()
    rds.get_paginator.return_value = paginator
    mock = MagicMock()
    mock.client.return_value = rds
    return mock


def test_lists_only_mysql_sorted(session: MagicMock) -> None:
    """Postgres is filtered out and the rest come back ordered by identifier."""
    instances = RDSMySQLInstance.list_instances(session=session)
    assert [i.db_instance_id for i in instances] == ["mysql-one", "mysql-two"]


def test_every_engine_when_prefix_is_empty(session: MagicMock) -> None:
    """An empty prefix disables the engine filter."""
    instances = RDSMySQLInstance.list_instances(engine_prefix="", session=session)
    assert len(instances) == 3


def test_returned_instances_need_no_extra_api_call(session: MagicMock) -> None:
    """The description is seeded from the bulk call, so reads are free."""
    instances = RDSMySQLInstance.list_instances(session=session)
    rds = session.client.return_value
    rds.describe_db_instances.reset_mock()

    assert instances[1].engine == "mysql"
    assert instances[1].engine_version == "8.0.45"
    assert instances[1].status == "available"
    assert instances[1].tags == {"service": "second-service"}
    rds.describe_db_instances.assert_not_called()


def test_tags_without_tag_list(session: MagicMock) -> None:
    """An instance with no tags yields an empty dict, not an error."""
    instances = RDSMySQLInstance.list_instances(engine_prefix="postgres", session=session)
    assert instances[0].tags == {}


def test_empty_account(session: MagicMock) -> None:
    """No instances is an empty list, not an exception."""
    session.client.return_value.get_paginator.return_value.paginate.return_value = [{"DBInstances": []}]
    assert RDSMySQLInstance.list_instances(session=session) == []
