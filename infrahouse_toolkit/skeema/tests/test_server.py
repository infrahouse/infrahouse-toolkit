"""Unit tests for :py:mod:`infrahouse_toolkit.skeema.server`."""

from unittest import mock

import pytest

from infrahouse_toolkit.skeema.server import MySQLServer


@pytest.fixture(name="connect")
def _connect():
    """Patch pymysql.connect so that no database is queried."""
    with mock.patch("infrahouse_toolkit.skeema.server.pymysql.connect") as connect:
        yield connect


@pytest.fixture(name="cursor")
def _cursor(connect):
    """The cursor queries run on."""
    return connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value


def test_threads_running(connect, cursor):
    """Threads_running is read from the host and port skeema prints."""
    cursor.fetchall.return_value = (("Threads_running", "12"),)

    assert MySQLServer("db.example.com:3307", "admin", "pa,ss#word").threads_running == 12
    connect.assert_called_once_with(host="db.example.com", port=3307, user="admin", password="pa,ss#word")


def test_leftovers(cursor):
    """Shadow tables and pt-osc triggers are found with underscores matched literally."""
    cursor.fetchall.side_effect = [
        (("shop", "_orders_new"), ("shop", "_orders_old")),
        (("shop", "pt_osc_shop_orders_ins"),),
    ]

    leftovers = MySQLServer("db:3306", "admin", "secret").leftovers(["other", "shop"])

    assert [(item.instance, item.schema, item.kind, item.name) for item in leftovers] == [
        ("db:3306", "shop", "table", "_orders_new"),
        ("db:3306", "shop", "table", "_orders_old"),
        ("db:3306", "shop", "trigger", "pt_osc_shop_orders_ins"),
    ]
    tables_args = cursor.execute.call_args_list[0].args[1]
    triggers_args = cursor.execute.call_args_list[1].args[1]
    # Unescaped, _%_new would also match a table named "renew".
    assert tables_args == (["other", "shop"], "\\_%\\_new", "\\_%\\_old")
    assert triggers_args == (["other", "shop"], "pt\\_osc\\_%")


def test_table_sizes(cursor):
    """Sizes are keyed by schema and table."""
    cursor.fetchall.return_value = (("shop", "orders", 3178496), ("shop", "small", 16384))

    assert MySQLServer("db:3306", "admin", "secret").table_sizes(["shop"]) == {
        ("shop", "orders"): 3178496,
        ("shop", "small"): 16384,
    }
