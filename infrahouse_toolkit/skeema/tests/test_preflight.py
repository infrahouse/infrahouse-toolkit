"""Unit tests for :py:mod:`infrahouse_toolkit.skeema.preflight`."""

from unittest import mock

import pytest

from infrahouse_toolkit.skeema.diff import SkeemaDiff
from infrahouse_toolkit.skeema.exceptions import SkeemaDiffError, SkeemaError
from infrahouse_toolkit.skeema.leftover import Leftover
from infrahouse_toolkit.skeema.preflight import NO_WRAPPERS, Preflight
from infrahouse_toolkit.skeema.tests.conftest import (
    DIFF_ERRORS,
    PLAIN_OUTPUT,
    WORKING_DIR,
)

INSTANCE = "127.0.0.1:33069"
SIZES = {
    ("other", "t"): 16384,
    ("shop", "gone"): 16384,
    ("shop", "orders"): 3178496,
    ("shop", "small"): 32768,
}


@pytest.fixture(name="server")
def _server():
    """Patch MySQLServer so that no database is queried."""
    with mock.patch("infrahouse_toolkit.skeema.preflight.MySQLServer") as server_class:
        server = server_class.return_value
        server.threads_running = 7
        server.table_sizes.return_value = SIZES
        server.leftovers.return_value = []
        yield server


def _skeema(*diffs):
    """
    A skeema whose consecutive diff runs return the given diffs.

    :param diffs: Diffs to return.
    :return: The mock skeema.
    """
    skeema = mock.MagicMock()
    skeema.diff.side_effect = list(diffs)
    return skeema


def _routes(preflight):
    """
    :param preflight: The preflight.
    :return: (schema, table, operation, size, wrapped) of every change.
    """
    return [(c.schema, c.table, c.operation, c.size, c.wrapped) for c in preflight.changes]


def test_changes_with_wrapper(server, configured_diff, plain_diff):  # pylint: disable=unused-argument
    """The change without a plain statement in the configured diff is the wrapped one."""
    skeema = _skeema(configured_diff, plain_diff)
    preflight = Preflight(skeema, "production", ["--allow-unsafe"])

    assert _routes(preflight) == [
        ("other", "t", "ALTER", 16384, False),
        ("shop", "fresh", "CREATE", None, False),
        ("shop", "gone", "DROP", 16384, False),
        ("shop", "orders", "ALTER", 3178496, True),
        ("shop", "small", "ALTER", 32768, False),
    ]
    assert skeema.diff.call_args_list == [
        mock.call(["production", "--allow-unsafe"]),
        mock.call(["production", "--allow-unsafe"] + NO_WRAPPERS),
    ]


def test_changes_without_wrapper(server, plain_diff):  # pylint: disable=unused-argument
    """Without wrapper commands every change is plain, and one diff is enough."""
    skeema = _skeema(plain_diff)
    preflight = Preflight(skeema, "production", [])

    assert not any(change.wrapped for change in preflight.changes)
    assert len(preflight.changes) == 5
    skeema.diff.assert_called_once_with(["production"])


def test_changes_when_diffs_disagree(server, configured_diff):  # pylint: disable=unused-argument
    """A table changed between the two diffs can't be told apart from a wrapped one, so it's an error."""
    grown = SkeemaDiff(
        PLAIN_OUTPUT.replace("DROP TABLE `gone`;", "DROP TABLE `gone`;\nALTER TABLE `late` ADD COLUMN `y` int;"),
        DIFF_ERRORS,
        1,
        WORKING_DIR,
    )
    preflight = Preflight(_skeema(configured_diff, grown), "production", [])

    with pytest.raises(SkeemaError, match="changed between the two diffs"):
        _ = preflight.changes


def test_changes_of_failed_diff(server, refused_diff):  # pylint: disable=unused-argument
    """A failed diff lists only part of the changes, so it lists none."""
    with pytest.raises(SkeemaDiffError):
        _ = Preflight(_skeema(refused_diff), "production", []).changes


def test_markdown(server, configured_diff, plain_diff):
    """The report routes each table and ends with the diff and its digest."""
    markdown = Preflight(_skeema(configured_diff, plain_diff), "production", []).markdown

    assert f"| `{INSTANCE}` | 7 |" in markdown
    assert f"| `{INSTANCE}` | `shop` | `orders` | ALTER | 3.0 MiB | alter-wrapper |" in markdown
    assert f"| `{INSTANCE}` | `shop` | `fresh` | CREATE | - | plain |" in markdown
    assert "### Leftovers of an interrupted online schema change\n\nNone." in markdown
    assert f"~~~sql\n{configured_diff.output}~~~" in markdown
    assert markdown.endswith(f"### Digest\n\n`{configured_diff.digest}`\n")
    server.leftovers.assert_called_once_with(["other", "shop"])


def test_markdown_of_failed_diff(server, refused_diff):
    """When skeema refuses a schema, the report still shows the leftovers that likely caused it."""
    server.leftovers.return_value = [
        Leftover(INSTANCE, "shop", "table", "_orders_old"),
        Leftover(INSTANCE, "shop", "trigger", "pt_osc_shop_orders_ins"),
    ]
    skeema = _skeema(refused_diff)

    markdown = Preflight(skeema, "production", []).markdown

    assert "**skeema diff failed with exit code 2, so a push would fail too.**" in markdown
    assert "### Table changes\n\nNot available because skeema diff failed." in markdown
    assert f"| `{INSTANCE}` | `shop` | table | `_orders_old` |" in markdown
    assert f"| `{INSTANCE}` | `shop` | trigger | `pt_osc_shop_orders_ins` |" in markdown
    assert "[ERROR] # DROP TABLE `_orders_old`" in markdown
    assert markdown.endswith("### Digest\n\nNot available because skeema diff failed.\n")
    # The refused schema is checked for leftovers even though skeema printed nothing for it.
    server.leftovers.assert_called_once_with(["other", "shop"])
    skeema.diff.assert_called_once()


@pytest.mark.parametrize(
    "size, text",
    [(None, "-"), (512, "512 B"), (16384, "16.0 KiB"), (3178496, "3.0 MiB"), (5 * 1024**4, "5.0 TiB")],
)
def test_format_size(size, text):
    """Sizes read in binary units."""
    # pylint: disable=protected-access
    assert Preflight._format_size(size) == text
