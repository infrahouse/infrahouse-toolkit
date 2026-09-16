"""
.. topic:: ``ih-skeema preflight``

    A ``ih-skeema preflight`` subcommand.

    See ``ih-skeema preflight --help`` for more details.
"""

import sys
from logging import getLogger

import click
from pymysql import MySQLError

from infrahouse_toolkit import DEFAULT_OPEN_ENCODING
from infrahouse_toolkit.skeema import EXIT_ERROR, Preflight, SkeemaError

LOG = getLogger(__name__)


@click.command(
    name="preflight",
    short_help="Report what a push would do and what it would cost.",
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
@click.option(
    "--digest-file",
    help="Also write the digest of the pending changes to this file, for ih-skeema run push --expect-digest.",
    default=None,
)
@click.argument("environment")
@click.pass_context
def cmd_preflight(ctx, environment, digest_file):
    """
    Report what skeema push to ENVIRONMENT would do and what it would cost.

    Prints a Markdown report to stdout: for every table change, the table size and whether
    skeema hands it to the alter-wrapper; leftovers of an interrupted pt-online-schema-change;
    Threads_running of every server; the diff itself and its digest.

    Extra arguments go to skeema diff. Pass the ones the push will get, or the digest won't match.

    Exits with the codes skeema diff uses: 0 for no differences, 1 for differences,
    2 or more for errors. The report is still printed when skeema diff fails.
    """
    try:
        preflight = Preflight(ctx.obj["skeema"], environment, ctx.args)
        print(preflight.markdown, end="")
        if digest_file and not preflight.diff.failed:
            with open(digest_file, "w", encoding=DEFAULT_OPEN_ENCODING) as handle:
                handle.write(preflight.diff.digest + "\n")

    except (SkeemaError, MySQLError) as err:
        LOG.error("%s", err)
        sys.exit(EXIT_ERROR)

    sys.exit(preflight.diff.returncode)
