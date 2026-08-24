"""Tests for :class:`infrahouse_toolkit.aws.rds.QueryDigest`."""

from datetime import datetime, timezone
from subprocess import CalledProcessError
from unittest.mock import MagicMock, patch

import pytest

from infrahouse_toolkit.aws.rds import QueryDigest, QueryDigestError


def test_command_defaults() -> None:
    """The default report ranks queries by total time."""
    assert QueryDigest(["slow.log"]).command() == [
        "pt-query-digest",
        "--group-by",
        "fingerprint",
        "--order-by",
        "Query_time:sum",
        "--limit",
        "20",
        "slow.log",
    ]


def test_command_with_since_and_filter() -> None:
    """--since drops events RDS wrote to the file before the capture began."""
    digest = QueryDigest(
        ["a.log", "b.log"],
        since=datetime(2026, 8, 24, 14, 30, 0, tzinfo=timezone.utc),
    )
    command = digest.command(group_by="tables", query_filter="$event->{arg} =~ m/fetch_results/")
    assert "--since" in command
    assert command[command.index("--since") + 1] == "2026-08-24 14:30:00"
    assert command[command.index("--group-by") + 1] == "tables"
    assert command[command.index("--filter") + 1] == "$event->{arg} =~ m/fetch_results/"
    assert command[-2:] == ["a.log", "b.log"]


def test_command_without_log_files() -> None:
    """A capture that produced nothing must not silently digest nothing."""
    with pytest.raises(QueryDigestError) as exc_info:
        QueryDigest([]).command()
    assert "No slow log files" in str(exc_info.value)


def test_report_writes_output(tmp_path) -> None:
    """Whatever pt-query-digest prints lands in the report file."""
    result = MagicMock()
    result.stdout = "# Profile\n"
    destination = tmp_path / "digest.txt"
    with patch("infrahouse_toolkit.aws.rds.query_digest.run", return_value=result):
        assert QueryDigest(["slow.log"]).report(str(destination)) == str(destination)
    assert destination.read_text() == "# Profile\n"


def test_report_without_percona_toolkit(tmp_path) -> None:
    """A missing binary says how to install it."""
    with patch("infrahouse_toolkit.aws.rds.query_digest.run", side_effect=FileNotFoundError):
        with pytest.raises(QueryDigestError) as exc_info:
            QueryDigest(["slow.log"]).report(str(tmp_path / "digest.txt"))
    assert "percona-toolkit" in str(exc_info.value)


def test_report_when_digest_fails(tmp_path) -> None:
    """A non-zero exit carries the tool's own stderr."""
    error = CalledProcessError(returncode=2, cmd="pt-query-digest", stderr="bad --filter")
    with patch("infrahouse_toolkit.aws.rds.query_digest.run", side_effect=error):
        with pytest.raises(QueryDigestError) as exc_info:
            QueryDigest(["slow.log"]).report(str(tmp_path / "digest.txt"))
    assert "bad --filter" in str(exc_info.value)


# What RDS leaves in a freshly created slow log file before any query is logged.
HEADER = (
    "/rdsdbbin/mysql/bin/mysqld, Version: 8.0.45 (Source distribution). started with:\n"
    "Tcp port: 3306  Unix socket: /tmp/mysql.sock\n"
    "Time                 Id Command    Argument\n"
)

EVENT = (
    "# Time: 2026-08-24T17:40:00.000000Z\n"
    "# User@Host: app[app] @  [10.0.0.1]  Id:    42\n"
    "# Query_time: 0.000512  Lock_time: 0.000001 Rows_sent: 1  Rows_examined: 1\n"
    "SET timestamp=1756056000;\n"
    "SELECT 1;\n"
)


def test_event_count_ignores_the_header(tmp_path) -> None:
    """A capture that logged nothing still leaves a non-empty file — that is not a capture."""
    log = tmp_path / "slow.log"
    log.write_text(HEADER)
    assert log.stat().st_size > 0
    assert QueryDigest([str(log)]).event_count == 0


def test_event_count_counts_queries(tmp_path) -> None:
    """Each logged query is one event."""
    log = tmp_path / "slow.log"
    log.write_text(HEADER + EVENT + EVENT)
    assert QueryDigest([str(log)]).event_count == 2


def test_event_count_across_rotated_files(tmp_path) -> None:
    """RDS rotates hourly, so a long capture spans several files."""
    first = tmp_path / "slow.log.1"
    first.write_text(HEADER + EVENT)
    second = tmp_path / "slow.log.2"
    second.write_text(HEADER + EVENT + EVENT)
    assert QueryDigest([str(first), str(second)]).event_count == 3


def test_event_count_without_log_files() -> None:
    """No files means no events, not an error."""
    assert QueryDigest([]).event_count == 0
