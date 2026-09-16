"""
Module for Statement class - one statement of ``skeema diff`` output.
"""

import re
from typing import Optional

# skeema quotes identifiers in backticks and doubles a backtick inside a name.
TABLE_STATEMENT = re.compile(r"^(?P<operation>ALTER|CREATE|DROP) TABLE `(?P<table>(?:[^`]|``)+)`")
WRAPPER_PREFIX = "\\!"


class Statement:
    """
    One statement of ``skeema diff`` output and where it applies.

    :param instance: Instance the statement is for, as skeema prints it, e.g. ``db.example.com:3306``.
    :type instance: str
    :param schema: Schema the statement is for.
    :type schema: str
    :param text: The statement as skeema printed it. It may span several lines.
    :type text: str
    """

    def __init__(self, instance: str, schema: str, text: str):
        self._instance = instance
        self._schema = schema
        self._text = text

    # --- Public properties ---

    @property
    def instance(self) -> str:
        """
        :return: Instance the statement is for.
        :rtype: str
        """
        return self._instance

    @property
    def is_wrapped(self) -> bool:
        """
        :return: ``True`` if skeema hands the change to an external command (``alter-wrapper``)
            instead of running the statement.
        :rtype: bool
        """
        return self._text.startswith(WRAPPER_PREFIX)

    @property
    def operation(self) -> Optional[str]:
        """
        :return: ``ALTER``, ``CREATE`` or ``DROP`` for a table statement. ``None`` for anything
            else: a wrapper command, whose table only its template knows, or a stored routine.
        :rtype: str
        """
        match = TABLE_STATEMENT.match(self._text)
        return match.group("operation") if match else None

    @property
    def schema(self) -> str:
        """
        :return: Schema the statement is for.
        :rtype: str
        """
        return self._schema

    @property
    def table(self) -> Optional[str]:
        """
        :return: Name of the table a table statement changes, ``None`` for any other statement.
        :rtype: str
        """
        match = TABLE_STATEMENT.match(self._text)
        return match.group("table").replace("``", "`") if match else None

    @property
    def text(self) -> str:
        """
        :return: The statement as skeema printed it.
        :rtype: str
        """
        return self._text
