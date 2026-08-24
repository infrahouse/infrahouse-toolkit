"""
.. topic:: ``ih-mysql query-audit``

    Capture and digest the slow query log of an RDS for MySQL instance.

    The workflow is::

        ih-mysql query-audit status   <instance-id>   # what is configured now
        ih-mysql query-audit capture  <instance-id>   # turn it up, wait, pull, restore
        ih-mysql query-audit digest   <log-file>...   # re-slice an existing capture
        ih-mysql query-audit restore  --state-file …  # undo a capture that died

    See ``ih-mysql query-audit --help`` for more details.
"""

import sys
from logging import getLogger

import click
from botocore.exceptions import NoRegionError
from infrahouse_core.aws import get_aws_session
from infrahouse_core.aws.config import AWSConfig

from infrahouse_toolkit.cli.ih_mysql.cmd_query_audit.cmd_capture import cmd_capture
from infrahouse_toolkit.cli.ih_mysql.cmd_query_audit.cmd_digest import cmd_digest
from infrahouse_toolkit.cli.ih_mysql.cmd_query_audit.cmd_restore import cmd_restore
from infrahouse_toolkit.cli.ih_mysql.cmd_query_audit.cmd_status import cmd_status

LOG = getLogger(__name__)


@click.group(name="query-audit")
@click.pass_context
def cmd_query_audit(ctx):
    """Slow query log capture and analysis for RDS for MySQL."""
    # Built here rather than in the ih-mysql group so that bootstrap and
    # failover, which run from Puppet on instance boot, keep working without an
    # STS round-trip on every invocation.
    try:
        ctx.obj["aws_session"] = get_aws_session(AWSConfig(), ctx.obj["aws_profile"], ctx.obj["aws_region"])
    except NoRegionError as err:
        LOG.error(err)
        LOG.error("Use the --aws-region option to specify the AWS region.")
        sys.exit(1)


for command in [cmd_status, cmd_capture, cmd_digest, cmd_restore]:
    # noinspection PyTypeChecker
    cmd_query_audit.add_command(command)
