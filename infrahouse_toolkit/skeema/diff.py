"""
Module for SkeemaDiff class - the result of one ``skeema diff`` run.
"""

import json
import re
import shlex
from hashlib import sha256
from typing import List, Tuple

from infrahouse_toolkit import DEFAULT_ENCODING
from infrahouse_toolkit.skeema.exceptions import SkeemaDiffError, SkeemaDigestMismatch
from infrahouse_toolkit.skeema.statement import WRAPPER_PREFIX, Statement

INSTANCE_PREFIX = "-- instance: "
USE_STATEMENT = re.compile(r"^USE `(?P<schema>(?:[^`]|``)+)`;$")
DELIMITER_STATEMENT = re.compile(r"^DELIMITER (?P<delimiter>\S+)$")

# skeema logs to stderr, e.g.
# 2026-09-16 11:52:35 [INFO]  Generating diff of 127.0.0.1:3306 shop vs /work/schema/shop/*.sql
LOG_LINE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \[(?P<level>[A-Z]+)\]\s+(?P<message>.*)$")
GENERATING_DIFF = re.compile(r"^Generating diff of (?P<instance>\S+) (?P<schema>\S+) vs ")

WORKING_DIR_PLACEHOLDER = "{WORKING_DIR}"


class SkeemaDiff:
    """
    The result of one ``skeema diff`` run.

    :param output: What skeema printed to stdout: the DDL.
    :type output: str
    :param errors: What skeema printed to stderr: its log.
    :type errors: str
    :param returncode: skeema exit code. 0 means no differences, 1 differences, 2 or more a failure.
    :type returncode: int
    :param working_dir: Directory skeema ran in.
    :type working_dir: str
    """

    def __init__(self, output: str, errors: str, returncode: int, working_dir: str):
        self._output = output
        self._errors = errors
        self._returncode = returncode
        self._working_dir = working_dir

    # --- Public properties ---

    @property
    def digest(self) -> str:
        """
        A digest of the pending changes that is stable between runs and CI workers.

        Hashing the output as is would not work. skeema prints the statements of a schema in a
        different order from one run to the next, and an ``alter-wrapper`` template may render
        the working directory (``{DIRPATH}``). So the digest covers the set of statements per
        instance and schema, with the working directory masked.

        The digest detects a change; it does not pin one. A push works the diff out again when it runs.

        :return: SHA-256 hex digest.
        :rtype: str
        :raises SkeemaDiffError: If skeema diff failed. The output then misses whatever skeema refused.
        """
        if self.failed:
            raise SkeemaDiffError(
                f"skeema diff exited with code {self._returncode}; "
                "there is no complete diff to digest:\n" + "\n".join(self.problems)
            )
        canonical = sorted(
            [statement.instance, statement.schema, statement.text.replace(self._working_dir, WORKING_DIR_PLACEHOLDER)]
            for statement in self.statements
        )
        return sha256(json.dumps(canonical).encode(DEFAULT_ENCODING)).hexdigest()

    @property
    def errors(self) -> str:
        """
        :return: What skeema printed to stderr.
        :rtype: str
        """
        return self._errors

    @property
    def failed(self) -> bool:
        """
        :return: ``True`` if skeema diff exited with code 2 or more. That includes a schema skipped
            because of unsafe statements: skeema then prints nothing for that schema.
        :rtype: bool
        """
        return self._returncode >= 2

    @property
    def output(self) -> str:
        """
        :return: What skeema printed to stdout.
        :rtype: str
        """
        return self._output

    @property
    def problems(self) -> List[str]:
        """
        :return: Messages skeema logged at WARN or ERROR level, without timestamps.
        :rtype: list
        """
        problems = []
        for line in self._errors.splitlines():
            match = LOG_LINE.match(line)
            if match and match.group("level") in ("WARN", "ERROR"):
                problems.append(f"[{match.group('level')}] {match.group('message')}")
        return problems

    @property
    def returncode(self) -> int:
        """
        :return: skeema exit code.
        :rtype: int
        """
        return self._returncode

    @property
    def schemas(self) -> List[Tuple[str, str]]:
        """
        Every schema skeema compared, including those it skipped and those without differences.

        These come from the log, because stdout says nothing about a schema skeema refused
        to diff.

        :return: ``(instance, schema)`` pairs in the order skeema compared them.
        :rtype: list
        """
        schemas = []
        for line in self._errors.splitlines():
            log_match = LOG_LINE.match(line)
            if log_match:
                match = GENERATING_DIFF.match(log_match.group("message"))
                if match:
                    schemas.append((match.group("instance"), match.group("schema")))
        return schemas

    @property
    def statements(self) -> List[Statement]:
        """
        :return: Statements in the order skeema printed them.
        :rtype: list
        :raises SkeemaDiffError: If the output ends in the middle of a statement.
        """
        statements = []
        instance = schema = None
        delimiter = ";"
        lines = []
        for line in self._output.splitlines():
            if not lines:
                if line.startswith(INSTANCE_PREFIX):
                    instance = line[len(INSTANCE_PREFIX) :]
                    continue
                use_match = USE_STATEMENT.match(line)
                if use_match:
                    schema = use_match.group("schema").replace("``", "`")
                    continue
                delimiter_match = DELIMITER_STATEMENT.match(line)
                if delimiter_match:
                    delimiter = delimiter_match.group("delimiter")
                    continue

            lines.append(line)
            text = "\n".join(lines)
            if self._is_complete(text, delimiter):
                statements.append(Statement(instance, schema, text))
                lines = []

        if lines:
            raise SkeemaDiffError("skeema diff output ends with an unterminated statement:\n" + "\n".join(lines))
        return statements

    # --- Public methods ---

    def verify_digest(self, expected: str) -> None:
        """
        Make sure the pending changes are the ones with the expected digest.

        :param expected: Digest reported by ``ih-skeema preflight``.
        :type expected: str
        :raises SkeemaDigestMismatch: If the changes are different.
        :raises SkeemaDiffError: If skeema diff failed.
        """
        if self.digest != expected:
            raise SkeemaDigestMismatch(
                f"The pending changes are not the ones approved: expected digest {expected}, got {self.digest}. "
                "Run ih-skeema preflight to review them."
            )

    # --- Protected methods ---

    @staticmethod
    def _is_complete(text: str, delimiter: str) -> bool:
        """
        Tell whether the lines read so far make a whole statement.

        A SQL statement ends with the delimiter. A wrapper command ends where its quotes balance:
        skeema quotes the values it renders into the template for the shell, so a clause that spans
        lines, such as a partition definition, keeps its newlines inside quotes.

        :param text: Lines of the statement read so far.
        :type text: str
        :param delimiter: Current statement delimiter.
        :type delimiter: str
        :return: ``True`` if the statement is complete.
        :rtype: bool
        """
        if not text.startswith(WRAPPER_PREFIX):
            return text.endswith(delimiter)
        try:
            shlex.split(text[len(WRAPPER_PREFIX) :])
        except ValueError:
            # No closing quotation: the command continues on the next line.
            return False
        return True
