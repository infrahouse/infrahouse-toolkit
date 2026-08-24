"""Tests for :class:`infrahouse_toolkit.cli.ih_mysql.cmd_query_audit.instance_list.InstanceList`."""

from unittest.mock import MagicMock, patch

import click
import pytest

from infrahouse_toolkit.cli.ih_mysql.cmd_query_audit.instance_list import InstanceList

LIST_INSTANCES = "infrahouse_toolkit.cli.ih_mysql.cmd_query_audit.instance_list.RDSMySQLInstance.list_instances"


def make_instance(identifier: str, tags: dict = None) -> MagicMock:
    """Return a mock RDSMySQLInstance the listing can render."""
    instance = MagicMock()
    instance.db_instance_id = identifier
    instance.engine = "mysql"
    instance.engine_version = "8.0.45"
    instance.status = "available"
    instance.tags = tags or {}
    instance.description = {"DBInstanceClass": "db.t3.large"}
    return instance


@pytest.fixture()
def listing() -> InstanceList:
    """Return a listing over two instances."""
    instances = [
        make_instance("mysql-one", {"Name": "first instance"}),
        make_instance("mysql-two", {"service": "second-service"}),
    ]
    result = InstanceList(MagicMock())
    with patch(LIST_INSTANCES, return_value=instances):
        _ = result.instances
    return result


def test_table_shows_a_row_per_instance(listing: InstanceList) -> None:
    """Both instances are listed with their class and state."""
    table = listing.table
    assert "mysql-one" in table
    assert "mysql-two" in table
    assert "db.t3.large" in table
    assert "available" in table


def test_table_prefers_name_tag_then_service(listing: InstanceList) -> None:
    """Name is the label when present; service is the fallback."""
    table = listing.table
    assert "first instance" in table
    assert "second-service" in table


def test_table_has_no_selection_numbers(listing: InstanceList) -> None:
    """Instances are chosen by identifier, so a number column would mislead."""
    assert listing.table.splitlines()[1].strip().startswith("| Name")


def test_require_resolves_a_given_identifier(listing: InstanceList) -> None:
    """A supplied identifier is used directly, without listing anything."""
    with patch("infrahouse_toolkit.cli.ih_mysql.cmd_query_audit.instance_list.RDSMySQLInstance") as mock_instance:
        assert listing.require("some-db") is mock_instance.return_value
    mock_instance.assert_called_once()


def test_require_without_identifier_lists_choices(listing: InstanceList) -> None:
    """A missing argument fails with the valid identifiers, not a prompt."""
    with pytest.raises(click.UsageError) as exc_info:
        listing.require(None)
    message = str(exc_info.value)
    assert "Missing argument 'INSTANCE_ID'" in message
    assert "mysql-one" in message
    assert "mysql-two" in message


def test_require_without_identifier_and_no_instances() -> None:
    """An empty region says so rather than printing an empty table."""
    listing = InstanceList(MagicMock())
    with patch(LIST_INSTANCES, return_value=[]):
        with pytest.raises(click.UsageError) as exc_info:
            listing.require(None)
    assert "no RDS for MySQL instances were found" in str(exc_info.value)
