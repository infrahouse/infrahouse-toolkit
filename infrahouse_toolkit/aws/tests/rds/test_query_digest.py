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
