"""Unit tests for :py:mod:`infrahouse_toolkit.skeema.diff`."""

import pytest

from infrahouse_toolkit.skeema.diff import SkeemaDiff
from infrahouse_toolkit.skeema.exceptions import SkeemaDiffError, SkeemaDigestMismatch
from infrahouse_toolkit.skeema.tests.conftest import (
    CONFIGURED_OUTPUT,
    DIFF_ERRORS,
    WORKING_DIR,
)


def test_statements(configured_diff):
    """Every statement is attributed to its instance and schema, whatever lines it spans."""
    statements = configured_diff.statements

    assert [(s.instance, s.schema, s.text.splitlines()[0]) for s in statements] == [
        ("127.0.0.1:33069", "other", "ALTER TABLE `t` ADD COLUMN `x` int DEFAULT NULL;"),
        ("127.0.0.1:33069", "shop", "DROP TABLE `gone`;"),
        (
            "127.0.0.1:33069",
            "shop",
            "\\! /usr/bin/pt-online-schema-change --execute --alter 'ADD COLUMN `note` varchar(255) DEFAULT NULL' "
            "D=shop,t=orders,h=127.0.0.1,P=33069,F=$IH_SKEEMA_DEFAULTS_FILE",
        ),
        ("127.0.0.1:33069", "shop", "ALTER TABLE `small` ADD COLUMN `w` int DEFAULT NULL;"),
        ("127.0.0.1:33069", "shop", "CREATE TABLE `fresh` ("),
        ("127.0.0.1:33069", "shop", "CREATE DEFINER=`root`@`%` PROCEDURE `proc_touch`(IN p_id int)"),
    ]
    assert statements[4].text.endswith(") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;")
    # A statement inside a routine body ends with ";" but doesn't end the routine.
    assert statements[5].text.endswith("  SELECT 1;\nEND//")


def test_statements_on_several_instances():
    """Each instance block starts over with its own schemas."""
    output = (
        "-- instance: db1:3306\nUSE `shop`;\nDROP TABLE `gone`;\n"
        "-- instance: db2:3306\nUSE `shop`;\nDROP TABLE `gone`;\n"
    )

    statements = SkeemaDiff(output, "", 1, WORKING_DIR).statements

    assert [(s.instance, s.schema, s.text) for s in statements] == [
        ("db1:3306", "shop", "DROP TABLE `gone`;"),
        ("db2:3306", "shop", "DROP TABLE `gone`;"),
    ]


def test_multiline_wrapper_command():
    """A wrapper command ends where its quotes balance, not at the end of its first line."""
    output = (
        "-- instance: db1:3306\nUSE `shop`;\n"
        "\\! pt-online-schema-change --alter '/*!50500 PARTITION BY RANGE  COLUMNS(created_at)\n"
        "(PARTITION pmax VALUES LESS THAN (MAXVALUE) ENGINE = InnoDB) */' D=shop,t=small\n"
        # A quote inside a clause is escaped for the shell and doesn't open a new quoted string.
        "\\! pt-online-schema-change --alter 'COMMENT '\"'\"'it'\"'\"'s'\"'\"'' D=shop,t=orders\n"
        "DROP TABLE `gone`;\n"
    )

    statements = SkeemaDiff(output, "", 1, WORKING_DIR).statements

    assert [s.text.splitlines()[-1] for s in statements] == [
        "(PARTITION pmax VALUES LESS THAN (MAXVALUE) ENGINE = InnoDB) */' D=shop,t=small",
        "\\! pt-online-schema-change --alter 'COMMENT '\"'\"'it'\"'\"'s'\"'\"'' D=shop,t=orders",
        "DROP TABLE `gone`;",
    ]
    assert [s.is_wrapped for s in statements] == [True, True, False]


def test_unterminated_statement():
    """Output cut off in the middle of a statement is an error, not a shorter diff."""
    diff = SkeemaDiff("-- instance: db1:3306\nUSE `shop`;\nCREATE TABLE `fresh` (\n", "", 1, WORKING_DIR)

    with pytest.raises(SkeemaDiffError, match="unterminated statement"):
        _ = diff.statements


def test_schemas_include_refused_ones(refused_diff):
    """A schema skeema skipped prints nothing to stdout but still counts as compared."""
    assert refused_diff.schemas == [("127.0.0.1:33069", "other"), ("127.0.0.1:33069", "shop")]


def test_problems(refused_diff):
    """Warnings and errors are kept without timestamps, informational messages are not."""
    assert refused_diff.problems == [
        "[ERROR] Desired drop of table `_orders_old` would cause all of its data to be lost. "
        "Generated SQL statement:",
        "[ERROR] # DROP TABLE `_orders_old`",
        "[WARN] Skipping 127.0.0.1:33069 shop due to 1 unsafe statements. Use --allow-unsafe or "
        "--safe-below-size to permit this operation. Refer to the Safety Options section of --help.",
        "[ERROR] Skipped 1 operations due to problems",
    ]


def test_digest_ignores_statement_order(configured_diff):
    """skeema prints statements in varying order; the digest doesn't change."""
    lines = CONFIGURED_OUTPUT.splitlines()
    # Move DROP TABLE `gone` after ALTER TABLE `small`.
    reordered = lines[:4] + lines[5:7] + [lines[4]] + lines[7:]

    assert SkeemaDiff("\n".join(reordered) + "\n", DIFF_ERRORS, 1, WORKING_DIR).digest == configured_diff.digest


def test_digest_ignores_working_dir():
    """A wrapper template rendering {DIRPATH} gives the same digest on every CI worker."""
    template = "-- instance: db1:3306\nUSE `shop`;\n\\! {dir}/shop/../bin/osc D=shop,t=orders\n"

    first = SkeemaDiff(template.format(dir="/runner-1/work/schema"), "", 1, "/runner-1/work/schema")
    second = SkeemaDiff(template.format(dir="/home/runner/work/repo/schema"), "", 1, "/home/runner/work/repo/schema")

    assert first.digest == second.digest


def test_digest_ignores_log(configured_diff):
    """skeema log lines carry timestamps; they are not part of the changes."""
    assert SkeemaDiff(CONFIGURED_OUTPUT, "", 1, WORKING_DIR).digest == configured_diff.digest


@pytest.mark.parametrize(
    "changed_output",
    [
        # Different column type.
        CONFIGURED_OUTPUT.replace("ADD COLUMN `w` int", "ADD COLUMN `w` bigint"),
        # Same statement, different schema.
        CONFIGURED_OUTPUT.replace("USE `other`;", "USE `other2`;"),
        # One statement fewer.
        CONFIGURED_OUTPUT.replace("DROP TABLE `gone`;\n", ""),
    ],
)
def test_digest_detects_changes(configured_diff, changed_output):
    """Any change to what would be pushed changes the digest."""
    assert SkeemaDiff(changed_output, DIFF_ERRORS, 1, WORKING_DIR).digest != configured_diff.digest


def test_digest_of_failed_diff(refused_diff):
    """A failed diff misses what skeema refused, so it has no digest."""
    with pytest.raises(SkeemaDiffError, match="exited with code 2"):
        _ = refused_diff.digest


def test_verify_digest(configured_diff):
    """The digest a preflight reported passes."""
    configured_diff.verify_digest(configured_diff.digest)


def test_verify_digest_mismatch(configured_diff):
    """A different digest means the changes moved since approval."""
    with pytest.raises(SkeemaDigestMismatch, match="expected digest deadbeef"):
        configured_diff.verify_digest("deadbeef")
