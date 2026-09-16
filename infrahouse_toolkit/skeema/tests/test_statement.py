"""Unit tests for :py:mod:`infrahouse_toolkit.skeema.statement`."""

import pytest

from infrahouse_toolkit.skeema.statement import Statement


@pytest.mark.parametrize(
    "text, operation, table",
    [
        ("ALTER TABLE `orders` ADD COLUMN `note` varchar(255) DEFAULT NULL;", "ALTER", "orders"),
        ("CREATE TABLE `fresh` (\n  `id` int NOT NULL\n) ENGINE=InnoDB;", "CREATE", "fresh"),
        ("DROP TABLE `_orders_old`;", "DROP", "_orders_old"),
        # A backtick inside a name is doubled.
        ("DROP TABLE `odd``name`;", "DROP", "odd`name"),
    ],
)
def test_table_statement(text, operation, table):
    """A table statement tells what it does to which table."""
    statement = Statement("127.0.0.1:3306", "shop", text)

    assert (statement.operation, statement.table, statement.is_wrapped) == (operation, table, False)


def test_wrapper_command():
    """A wrapper command is wrapped, and its table is not readable from it."""
    statement = Statement(
        "127.0.0.1:3306",
        "shop",
        "\\! /usr/bin/pt-online-schema-change --alter 'ADD COLUMN `x` int' D=shop,t=orders",
    )

    assert statement.is_wrapped
    assert (statement.operation, statement.table) == (None, None)


def test_routine():
    """A stored routine is not a table statement."""
    statement = Statement("127.0.0.1:3306", "shop", "CREATE DEFINER=`root`@`%` PROCEDURE `p`()\nBEGIN\nEND//")

    assert (statement.operation, statement.table, statement.is_wrapped) == (None, None, False)
