"""
Module for Preflight class - what a skeema push would do, and what it would cost.
"""

from collections import Counter, defaultdict
from functools import cached_property
from typing import Dict, List, Optional, Tuple

from infrahouse_toolkit.skeema.diff import SkeemaDiff
from infrahouse_toolkit.skeema.exceptions import SkeemaDiffError, SkeemaError
from infrahouse_toolkit.skeema.leftover import Leftover
from infrahouse_toolkit.skeema.server import MySQLServer
from infrahouse_toolkit.skeema.skeema import Skeema
from infrahouse_toolkit.skeema.statement import Statement
from infrahouse_toolkit.skeema.table_change import TableChange

# Blanking both wrappers makes skeema print every change as a plain statement naming its table.
NO_WRAPPERS = ["--alter-wrapper=", "--ddl-wrapper="]


class Preflight:
    """
    What ``skeema push`` would do to an environment, and what it would cost.

    The same DDL can be a metadata-only change or hours of copying a table, depending only
    on whether skeema routes it to the ``alter-wrapper``. That depends on the table size and
    ``alter-wrapper-min-size``, and the statement itself doesn't show it.

    :param skeema: skeema executable to run.
    :type skeema: Skeema
    :param environment: skeema environment, e.g. ``production``.
    :type environment: str
    :param args: Other arguments for skeema diff. They must be the ones the push will get.
    :type args: list
    """

    def __init__(self, skeema: Skeema, environment: str, args: List[str]):
        self._skeema = skeema
        self._environment = environment
        self._args = args

    # --- Public properties ---

    @cached_property
    def changes(self) -> List[TableChange]:
        """
        Table changes, and whether skeema hands each one to the ``alter-wrapper``.

        A wrapper command names its table only in whatever form its template renders it, so a
        diff with wrappers can't be read back reliably. Instead, when the diff has any wrapper
        commands, the changes are listed from a second diff with wrappers blanked. A change
        that has no plain statement in the configured diff is one skeema wrapped. skeema
        applies ``alter-wrapper-min-size`` itself, so this report can't disagree with a push.

        :return: Table changes, ordered by instance, schema and table.
        :rtype: list
        :raises SkeemaDiffError: If skeema diff failed.
        :raises SkeemaError: If the two diffs disagree, i.e. the schema changed in between.
        """
        if self.diff.failed:
            raise SkeemaDiffError(f"skeema diff exited with code {self.diff.returncode}.")

        statements = self.diff.statements
        wrapped_count = sum(statement.is_wrapped for statement in statements)
        unwrapped = Counter(self._target(statement) for statement in statements if statement.operation)
        if wrapped_count:
            statements = self._plain_diff.statements

        routes = []
        for statement in statements:
            if statement.operation:
                target = self._target(statement)
                wrapped = unwrapped[target] == 0
                if not wrapped:
                    unwrapped[target] -= 1
                routes.append((statement, wrapped))

        missing_count = sum(wrapped for _, wrapped in routes)
        if missing_count != wrapped_count:
            raise SkeemaError(
                f"skeema printed {wrapped_count} wrapper commands, but {missing_count} table changes are missing "
                "from its plain statements. The schema must have changed between the two diffs; "
                "run the preflight again."
            )

        sizes = self._table_sizes([statement for statement, _ in routes])
        changes = []
        for statement, wrapped in routes:
            instance_sizes = sizes[statement.instance]
            size = None if statement.operation == "CREATE" else instance_sizes[statement.schema, statement.table]
            changes.append(TableChange(statement, wrapped, size))
        return sorted(changes, key=lambda change: (change.instance, change.schema, change.table))

    @cached_property
    def diff(self) -> SkeemaDiff:
        """
        :return: skeema diff with the configuration as is, i.e. what a push would do.
        :rtype: SkeemaDiff
        """
        return self._skeema.diff([self._environment] + self._args)

    @cached_property
    def leftovers(self) -> List[Leftover]:
        """
        :return: Shadow tables and triggers of an interrupted online schema change, in every schema
            skeema compared, including those it refused to diff.
        :rtype: list
        """
        schemas = defaultdict(list)
        for instance, schema in self.diff.schemas:
            schemas[instance].append(schema)
        return [
            leftover
            for instance, instance_schemas in schemas.items()
            for leftover in self.servers[instance].leftovers(instance_schemas)
        ]

    @property
    def markdown(self) -> str:
        """
        The report, ready to drop into a CI job summary. It is still produced when skeema diff
        fails, because the leftovers are often the reason it failed.

        :return: Markdown report.
        :rtype: str
        """
        lines = [f"## Skeema preflight: {self._environment}", ""]
        if self.diff.failed:
            lines.extend(
                [
                    f"**skeema diff failed with exit code {self.diff.returncode}, so a push would fail too.**",
                    "",
                ]
            )
        lines.extend(self._servers_markdown)
        lines.extend(self._changes_markdown)
        lines.extend(self._leftovers_markdown)
        lines.extend(self._problems_markdown)
        lines.extend(["### Diff", ""])
        lines.extend(["~~~sql", self.diff.output.rstrip("\n"), "~~~"] if self.diff.output else ["No statements."])
        lines.extend(["", "### Digest", ""])
        lines.append("Not available because skeema diff failed." if self.diff.failed else f"`{self.diff.digest}`")
        return "\n".join(lines) + "\n"

    @cached_property
    def servers(self) -> Dict[str, MySQLServer]:
        """
        :return: Servers skeema compared, by ``host:port``.
        :rtype: dict
        """
        return {
            instance: MySQLServer(instance, self._skeema.username, self._skeema.password)
            for instance, _ in self.diff.schemas
        }

    # --- Protected properties ---

    @property
    def _changes_markdown(self) -> List[str]:
        """
        :return: Markdown lines of the table changes section.
        :rtype: list
        """
        lines = ["### Table changes", ""]
        if self.diff.failed:
            return lines + ["Not available because skeema diff failed.", ""]
        if not self.changes:
            return lines + ["None.", ""]

        lines.extend(
            ["| Instance | Schema | Table | Operation | Size | Route |", "| --- | --- | --- | --- | ---: | --- |"]
        )
        for change in self.changes:
            lines.append(
                f"| `{change.instance}` | `{change.schema}` | `{change.table}` | {change.operation} "
                f"| {self._format_size(change.size)} | {'alter-wrapper' if change.wrapped else 'plain'} |"
            )
        return lines + [""]

    @property
    def _leftovers_markdown(self) -> List[str]:
        """
        :return: Markdown lines of the leftovers section.
        :rtype: list
        """
        lines = ["### Leftovers of an interrupted online schema change", ""]
        if not self.leftovers:
            return lines + ["None.", ""]

        lines.extend(
            [
                "Clear these before pushing. pt-online-schema-change refuses to run on a table that still has "
                "its triggers, and skeema will want to drop the shadow tables.",
                "",
                "| Instance | Schema | Kind | Name |",
                "| --- | --- | --- | --- |",
            ]
        )
        for leftover in self.leftovers:
            lines.append(f"| `{leftover.instance}` | `{leftover.schema}` | {leftover.kind} | `{leftover.name}` |")
        return lines + [""]

    @cached_property
    def _plain_diff(self) -> SkeemaDiff:
        """
        :return: skeema diff with wrappers blanked.
        :rtype: SkeemaDiff
        """
        return self._skeema.diff([self._environment] + self._args + NO_WRAPPERS)

    @property
    def _problems_markdown(self) -> List[str]:
        """
        :return: Markdown lines of the skeema warnings and errors section, if skeema logged any.
        :rtype: list
        """
        if not self.diff.problems:
            return []
        return ["### skeema warnings and errors", "", "~~~"] + self.diff.problems + ["~~~", ""]

    @property
    def _servers_markdown(self) -> List[str]:
        """
        :return: Markdown lines of the servers section.
        :rtype: list
        """
        lines = ["### Servers", "", "| Instance | Threads_running |", "| --- | ---: |"]
        for instance, server in self.servers.items():
            lines.append(f"| `{instance}` | {server.threads_running} |")
        return lines + [""]

    # --- Protected methods ---

    def _table_sizes(self, statements: List[Statement]) -> Dict[str, Dict[Tuple[str, str], int]]:
        """
        :param statements: Table statements.
        :type statements: list
        :return: Table sizes by instance, then by ``(schema, table)``, for the schemas the statements change.
        :rtype: dict
        """
        schemas = defaultdict(set)
        for statement in statements:
            schemas[statement.instance].add(statement.schema)
        return {
            instance: self.servers[instance].table_sizes(sorted(instance_schemas))
            for instance, instance_schemas in schemas.items()
        }

    @staticmethod
    def _format_size(size: Optional[int]) -> str:
        """
        :param size: Size in bytes, or ``None``.
        :type size: int
        :return: The size in binary units, or a dash for ``None``.
        :rtype: str
        """
        if size is None:
            return "-"
        value = float(size)
        for unit in ("B", "KiB", "MiB", "GiB"):
            if value < 1024:
                return f"{size} B" if unit == "B" else f"{value:.1f} {unit}"
            value /= 1024
        return f"{value:.1f} TiB"

    @staticmethod
    def _target(statement: Statement) -> Tuple[str, str, str, str]:
        """
        :param statement: A table statement.
        :type statement: Statement
        :return: What the statement changes: instance, schema, operation and table.
        :rtype: tuple
        """
        return statement.instance, statement.schema, statement.operation, statement.table
