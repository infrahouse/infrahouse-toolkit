"""
Module for MySQLServer class - a server skeema diffs against.
"""

from typing import Dict, List, Optional, Tuple

import pymysql

from infrahouse_toolkit.skeema.leftover import Leftover

# In LIKE an unescaped underscore matches any character, so _%_new would also match "renew".
LEFTOVER_TABLE_PATTERNS = ("\\_%\\_new", "\\_%\\_old")
LEFTOVER_TRIGGER_PATTERN = "pt\\_osc\\_%"


class MySQLServer:
    """
    A MySQL server skeema diffs against, queried for what the diff does not tell.

    :param address: ``host:port`` as skeema prints it in ``-- instance:``.
    :type address: str
    :param username: Database username.
    :type username: str
    :param password: Password for that user.
    :type password: str
    """

    def __init__(self, address: str, username: str, password: str):
        self._address = address
        self._username = username
        self._password = password

    # --- Public properties ---

    @property
    def address(self) -> str:
        """
        :return: ``host:port`` of the server.
        :rtype: str
        """
        return self._address

    @property
    def threads_running(self) -> int:
        """
        :return: Number of threads running right now, including the one asking.
        :rtype: int
        """
        ((_, value),) = self._query("SHOW GLOBAL STATUS LIKE 'Threads_running'")
        return int(value)

    # --- Public methods ---

    def leftovers(self, schemas: List[str]) -> List[Leftover]:
        """
        Find shadow tables and triggers an interrupted ``pt-online-schema-change`` left behind.

        :param schemas: Schemas to look in.
        :type schemas: list
        :return: Leftover tables, then leftover triggers.
        :rtype: list
        """
        tables = self._query(
            "SELECT TABLE_SCHEMA, TABLE_NAME FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA IN %s AND (TABLE_NAME LIKE %s OR TABLE_NAME LIKE %s) "
            "ORDER BY TABLE_SCHEMA, TABLE_NAME",
            (schemas, *LEFTOVER_TABLE_PATTERNS),
        )
        triggers = self._query(
            "SELECT TRIGGER_SCHEMA, TRIGGER_NAME FROM information_schema.TRIGGERS "
            "WHERE TRIGGER_SCHEMA IN %s AND TRIGGER_NAME LIKE %s "
            "ORDER BY TRIGGER_SCHEMA, TRIGGER_NAME",
            (schemas, LEFTOVER_TRIGGER_PATTERN),
        )
        return [Leftover(self._address, schema, "table", name) for schema, name in tables] + [
            Leftover(self._address, schema, "trigger", name) for schema, name in triggers
        ]

    def table_sizes(self, schemas: List[str]) -> Dict[Tuple[str, str], int]:
        """
        Size of every table in the given schemas, i.e. roughly what copying one takes.

        MySQL 8.0 caches these statistics for ``information_schema_stats_expiry`` seconds
        (a day by default), so they are estimates.

        :param schemas: Schemas to look in.
        :type schemas: list
        :return: ``DATA_LENGTH + INDEX_LENGTH`` in bytes by ``(schema, table)``.
        :rtype: dict
        """
        rows = self._query(
            "SELECT TABLE_SCHEMA, TABLE_NAME, DATA_LENGTH + INDEX_LENGTH FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA IN %s AND TABLE_TYPE = 'BASE TABLE'",
            (schemas,),
        )
        return {(schema, table): int(size) for schema, table, size in rows}

    # --- Protected methods ---

    def _query(self, query: str, args: Optional[tuple] = None) -> tuple:
        """
        Run a query on a connection of its own.

        :param query: SQL with ``%s`` placeholders.
        :type query: str
        :param args: Values for the placeholders.
        :type args: tuple
        :return: All rows.
        :rtype: tuple
        """
        host, port = self._address.rsplit(":", 1)
        with pymysql.connect(host=host, port=int(port), user=self._username, password=self._password) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, args)
                return cursor.fetchall()
