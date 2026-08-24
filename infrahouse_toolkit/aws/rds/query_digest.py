"""
``pt-query-digest`` wrapper.

Provides :class:`QueryDigest`, which turns downloaded slow log files into a
ranked query profile.  It lives next to the capture because the two are halves
of the same job: the capture produces logs nobody can read, the digest turns
them into an answer.
"""

from datetime import datetime
from logging import getLogger
from subprocess import CalledProcessError, run  # nosec B404
from typing import List

from infrahouse_toolkit import DEFAULT_OPEN_ENCODING
from infrahouse_toolkit.aws.rds.exceptions import QueryDigestError

LOG = getLogger(__name__)

PT_QUERY_DIGEST = "pt-query-digest"


class QueryDigest:
    """
    A ``pt-query-digest`` run over a set of slow log files.

    :param log_files: Slow log files to digest.
    :type log_files: List[str]
    :param since: Ignore events before this time.  Pass the capture start when
        digesting a log file that RDS had already been writing to, since the
        whole file comes down and the earlier part is not part of the window.
    :type since: datetime
    :param until: Ignore events after this time.
    :type until: datetime
    """

    def __init__(self, log_files: List[str], since: datetime = None, until: datetime = None) -> None:
        self._log_files = log_files
        self._since = since
        self._until = until

    # --- Public properties ---

    @property
    def event_count(self) -> int:
        """
        How many query events the log files actually contain.

        Not the same as "the files are non-empty": MySQL writes a few hundred
        bytes of preamble when it creates the slow log, so a capture that logged
        nothing at all still produces a file.  Counting ``# Query_time:`` lines
        is what distinguishes a real capture from an empty one.

        :return: Number of logged queries across all log files.
        :rtype: int
        """
        count = 0
        for path in self._log_files:
            with open(path, encoding=DEFAULT_OPEN_ENCODING, errors="replace") as descriptor:
                count += sum(1 for line in descriptor if line.startswith("# Query_time:"))
        return count

    @property
    def log_files(self) -> List[str]:
        """
        :return: Slow log files being digested.
        :rtype: List[str]
        """
        return self._log_files

    # --- Public methods ---

    def command(
        self,
        group_by: str = "fingerprint",
        order_by: str = "Query_time:sum",
        limit: str = "20",
        query_filter: str = None,
    ) -> List[str]:
        """
        Build the ``pt-query-digest`` command line.

        :param group_by: What to aggregate on — ``fingerprint`` for individual
            queries, ``tables`` for a per-table breakdown.
        :type group_by: str
        :param order_by: Ranking attribute, e.g. ``Query_time:sum`` or
            ``Rows_examined:sum``.
        :type order_by: str
        :param limit: How many classes to report, in ``pt-query-digest``
            syntax (``20``, ``95%:20``, ...).
        :type limit: str
        :param query_filter: Perl expression passed to ``--filter``, e.g.
            ``$event->{arg} =~ m/fetch_results/``.
        :type query_filter: str
        :return: Command line as a list.
        :rtype: List[str]
        :raises QueryDigestError: If there are no log files to digest.
        """
        if not self._log_files:
            raise QueryDigestError("No slow log files to digest")

        command = [
            PT_QUERY_DIGEST,
            "--group-by",
            group_by,
            "--order-by",
            order_by,
            "--limit",
            limit,
        ]
        if self._since:
            command += ["--since", self._format_time(self._since)]
        if self._until:
            command += ["--until", self._format_time(self._until)]
        if query_filter:
            command += ["--filter", query_filter]
        return command + self._log_files

    def report(  # pylint: disable=too-many-arguments
        self,
        output_path: str,
        group_by: str = "fingerprint",
        order_by: str = "Query_time:sum",
        limit: str = "20",
        query_filter: str = None,
    ) -> str:
        """
        Run ``pt-query-digest`` and write its report to a file.

        :param output_path: Where to write the report.
        :type output_path: str
        :param group_by: See :meth:`command`.
        :type group_by: str
        :param order_by: See :meth:`command`.
        :type order_by: str
        :param limit: See :meth:`command`.
        :type limit: str
        :param query_filter: See :meth:`command`.
        :type query_filter: str
        :return: *output_path*.
        :rtype: str
        :raises QueryDigestError: If ``pt-query-digest`` is missing or fails.
        """
        command = self.command(group_by=group_by, order_by=order_by, limit=limit, query_filter=query_filter)
        LOG.info("Running: %s", " ".join(command))
        try:
            result = run(command, capture_output=True, check=True, encoding=DEFAULT_OPEN_ENCODING)  # nosec B603
        except FileNotFoundError as err:
            raise QueryDigestError(
                f"{PT_QUERY_DIGEST} is not installed. Install percona-toolkit "
                f"(apt-get install percona-toolkit / brew install percona-toolkit)."
            ) from err
        except CalledProcessError as err:
            raise QueryDigestError(f"{PT_QUERY_DIGEST} exited with {err.returncode}: {err.stderr}") from err

        with open(output_path, "w", encoding=DEFAULT_OPEN_ENCODING) as descriptor:
            descriptor.write(result.stdout)
        LOG.info("Wrote %s", output_path)
        return output_path

    # --- Private methods ---

    @staticmethod
    def _format_time(moment: datetime) -> str:
        """
        Format a timestamp the way ``pt-query-digest`` expects.

        RDS writes slow log timestamps in UTC, so *moment* must be UTC too.

        :param moment: Timestamp to format.
        :type moment: datetime
        :return: ``YYYY-MM-DD HH:MM:SS``.
        :rtype: str
        """
        return moment.strftime("%Y-%m-%d %H:%M:%S")
