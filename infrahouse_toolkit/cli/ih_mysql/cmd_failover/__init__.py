"""
.. topic:: ``ih-mysql failover``

    Handle Orchestrator post-failover topology update.

    This command is invoked by Orchestrator's ``PostFailoverProcesses`` hook
    after a replica has been promoted to master.  It updates the NLB target
    groups, DynamoDB topology record, EC2 tags, and scale-in protection.

    See ``ih-mysql failover --help`` for more details.
"""

import sys
from logging import getLogger

import click

from infrahouse_toolkit.aws.mysql import (
    MySQLBootstrapError,
    MySQLInstanceNotFound,
    MySQLReplicaSet,
)

LOG = getLogger(__name__)


@click.command(name="failover")
@click.option("--cluster-id", required=True, help="Unique identifier for the Percona cluster.")
@click.option("--dynamodb-table", required=True, help="DynamoDB table name for topology records.")
@click.option(
    "--credentials-secret", required=True, help="AWS Secrets Manager secret name containing MySQL credentials."
)
@click.option("--vpc-cidr", required=True, help="VPC CIDR for MySQL user host restrictions (e.g., 10.0.0.0/16).")
@click.option("--read-tg-arn", default=None, help="ARN of the read target group.")
@click.option("--write-tg-arn", default=None, help="ARN of the write target group.")
@click.argument("failure_type")
@click.argument("failed_host")
@click.argument("successor_host")
@click.pass_context
def cmd_failover(
    ctx,
    cluster_id,
    dynamodb_table,
    credentials_secret,
    vpc_cidr,
    read_tg_arn,
    write_tg_arn,
    failure_type,
    failed_host,
    successor_host,
):  # pylint: disable=too-many-arguments
    """
    Handle Orchestrator post-failover topology update.

    Called by Orchestrator as::

        ih-mysql failover [OPTIONS] FAILURE_TYPE FAILED_HOST SUCCESSOR_HOST

    \b
    FAILURE_TYPE is logged but does not change behaviour.
    FAILED_HOST and SUCCESSOR_HOST are in ``host:port`` format.
    """
    # Orchestrator passes hosts in host:port format — strip the port.
    failed_host = failed_host.split(":")[0]
    successor_host = successor_host.split(":")[0]

    LOG.info("Failover triggered: type=%s failed=%s successor=%s", failure_type, failed_host, successor_host)

    replica_set = MySQLReplicaSet(
        cluster_id=cluster_id,
        dynamodb_table=dynamodb_table,
        credentials_secret=credentials_secret,
        vpc_cidr=vpc_cidr,
        aws_region=ctx.obj["aws_region"],
        read_tg_arn=read_tg_arn,
        write_tg_arn=write_tg_arn,
    )

    try:
        replica_set.handle_failover(failed_host, successor_host)
    except MySQLInstanceNotFound as err:
        LOG.error("%s", err)
        sys.exit(1)
    except MySQLBootstrapError as err:
        LOG.error("%s", err)
        sys.exit(1)

    LOG.info("Failover handling complete")
    sys.exit(0)
