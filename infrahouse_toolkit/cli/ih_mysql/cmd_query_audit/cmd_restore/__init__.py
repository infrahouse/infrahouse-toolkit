"""
.. topic:: ``ih-mysql query-audit restore``

    Undo a slow query log capture from its state file.

    ``capture`` restores parameters on its own way out, including on interrupt.
    This command is for when it could not: the process was killed outright, the
    laptop closed, or the restore API call itself failed. An instance left at
    ``long_query_time=0`` keeps filling its volume, so this is the emergency
    brake.

    See ``ih-mysql query-audit restore --help`` for more details.
"""

import sys
from logging import getLogger

import click
from botocore.exceptions import ClientError

from infrahouse_toolkit.aws.rds import RDSError, SlowLogCapture

LOG = getLogger(__name__)


@click.command(name="restore")
@click.option(
    "--state-file",
    help="State file written by ``ih-mysql query-audit capture``.",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
)
@click.pass_context
def cmd_restore(ctx, state_file):
    """
    Restore DB parameters recorded in a capture state file.

    Parameters that were explicitly set before the capture are set back to
    their old values; parameters that were merely inheriting a default are
    reset rather than pinned to it. The state file is removed on success.
    """
    try:
        instance_id = SlowLogCapture.restore_from_state_file(state_file, ctx.obj["aws_session"])
        LOG.info("Restored %s and removed %s", instance_id, state_file)
    except (RDSError, ClientError, OSError) as err:
        LOG.error("%s", err)
        LOG.error("The state file was left in place: %s", state_file)
        sys.exit(1)
