"""
Module for TableChange class - a change skeema would make to one table.
"""

from typing import Optional

from infrahouse_toolkit.skeema.statement import Statement


class TableChange:
    """
    A change skeema would make to one table.

    :param statement: The statement as a diff without wrappers prints it.
    :type statement: Statement
    :param wrapped: Whether skeema, as configured, hands the change to the ``alter-wrapper``.
    :type wrapped: bool
    :param size: ``DATA_LENGTH + INDEX_LENGTH`` in bytes. ``None`` for a table that does not exist yet.
    :type size: int
    """

    def __init__(self, statement: Statement, wrapped: bool, size: Optional[int]):
        self._statement = statement
        self._wrapped = wrapped
        self._size = size

    # --- Public properties ---

    @property
    def instance(self) -> str:
        """
        :return: Instance the table is on.
        :rtype: str
        """
        return self._statement.instance

    @property
    def operation(self) -> str:
        """
        :return: ``ALTER``, ``CREATE`` or ``DROP``.
        :rtype: str
        """
        return self._statement.operation

    @property
    def schema(self) -> str:
        """
        :return: Schema the table is in.
        :rtype: str
        """
        return self._statement.schema

    @property
    def size(self) -> Optional[int]:
        """
        :return: ``DATA_LENGTH + INDEX_LENGTH`` in bytes, ``None`` for a table that does not exist yet.
        :rtype: int
        """
        return self._size

    @property
    def table(self) -> str:
        """
        :return: Table name.
        :rtype: str
        """
        return self._statement.table

    @property
    def wrapped(self) -> bool:
        """
        :return: ``True`` if skeema hands the change to the ``alter-wrapper`` rather than running it.
        :rtype: bool
        """
        return self._wrapped
