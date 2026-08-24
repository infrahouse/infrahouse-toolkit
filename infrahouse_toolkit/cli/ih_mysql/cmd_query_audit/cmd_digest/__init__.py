"""
.. topic:: ``ih-mysql query-audit digest``

    Run ``pt-query-digest`` over slow log files that have already been
    downloaded.

    Useful for re-slicing a capture without repeating it — by table, by rows
    examined, or filtered down to the queries that touch one table.

    See ``ih-mysql query-audit digest --help`` for more details.
"""

import sys
from logging import getLogger

import click

from infrahouse_toolkit.aws.rds import QueryDigest, QueryDigestError
from infrahouse_toolkit.aws.rds.query_digest import PT_QUERY_DIGEST
from infrahouse_toolkit.cli.utils import check_dependencies

LOG = getLogger(__name__)


@click.command(name="digest")
@click.option(
    "--group-by",
    help="What to aggregate on. ``fingerprint`` ranks individual queries, ``tables`` gives the " "per-table breakdown.",
    default="fingerprint",
    show_default=True,
)
@click.option(
    "--order-by",
    help="Ranking attribute, e.g. Query_time:sum or Rows_examined:sum.",
    default="Query_time:sum",
    show_default=True,
)
@click.option(
    "--limit",
    help="How many query classes to report, in pt-query-digest syntax.",
    default="20",
    show_default=True,
)
@click.option(
    "--filter",
    "query_filter",
    help="Perl expression for pt-query-digest --filter, "
    "e.g. '$event->{arg} =~ m/fetch_results/' to keep only queries touching one table.",
    default=None,
)
@click.option(
    "--output",
    help="Write the report here instead of standard output.",
    default=None,
)
@click.argument("log_files", nargs=-1, required=True, type=click.Path(exists=True, dir_okay=False))
@click.pass_context
def cmd_digest(ctx, group_by, order_by, limit, query_filter, output, log_files):  # pylint: disable=too-many-arguments
    """
    Digest already-downloaded slow log files.

    LOG_FILES are slow log files as downloaded by ``query-audit capture``.
    """
    del ctx  # No AWS access needed; this runs entirely on local files.
    check_dependencies([PT_QUERY_DIGEST])
    try:
        digest = QueryDigest(list(log_files))
        destination = output or "/dev/stdout"
        digest.report(
            destination,
            group_by=group_by,
            order_by=order_by,
            limit=limit,
            query_filter=query_filter,
        )
    except QueryDigestError as err:
        LOG.error("%s", err)
        sys.exit(1)
