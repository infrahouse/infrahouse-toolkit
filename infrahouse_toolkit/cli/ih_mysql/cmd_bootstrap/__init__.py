"""
.. topic:: ``ih-mysql bootstrap``

    Bootstrap Percona/MySQL server as master or replica.

    This command coordinates master election via DynamoDB lock,
    creates MySQL users on master, configures replication on replicas,
    and registers instances with target groups.

    See ``ih-mysql bootstrap --help`` for more details.
"""

import sys
from logging import getLogger

import click
from botocore.exceptions import ClientError

from infrahouse_toolkit.aws.mysql import MySQLBootstrapError, MySQLReplicaSet

LOG = getLogger(__name__)


@click.command(name="bootstrap")
@click.option("--cluster-id", required=True, help="Unique identifier for the Percona cluster.")
@click.option("--dynamodb-table", required=True, help="DynamoDB table name for locking.")
@click.option(
    "--credentials-secret", required=True, help="AWS Secrets Manager secret name containing MySQL credentials."
)
@click.option("--vpc-cidr", required=True, help="VPC CIDR for MySQL user host restrictions (e.g., 10.0.0.0/16).")
@click.option(
    "--bootstrap-marker",
    default="/var/lib/mysql/.bootstrapped",
    show_default=True,
    help="Path to marker file indicating bootstrap completed.",
)
@click.option("--read-tg-arn", default=None, help="ARN of the read target group. All nodes will be registered.")
@click.option("--write-tg-arn", default=None, help="ARN of the write target group. Only master will be registered.")
@click.pass_context
def cmd_bootstrap(
    ctx, cluster_id, dynamodb_table, credentials_secret, vpc_cidr, bootstrap_marker, read_tg_arn, write_tg_arn
):  # pylint: disable=too-many-arguments
    """
    Bootstrap Percona server as master or replica.

    This command uses DynamoDB for distributed locking to coordinate
    master election. The first instance to acquire the lock becomes
    the master; subsequent instances become replicas.

    \b
    Master node:
    - Creates MySQL users (repl, backup, monitor)
    - Registers with write target group (if --write-tg-arn provided)

    \b
    Replica nodes:
    - Configures replication to master
    - Users are replicated from master automatically

    \b
    All nodes:
    - Register with read target group (if --read-tg-arn provided)
    """
    replica_set = MySQLReplicaSet(
        cluster_id=cluster_id,
        dynamodb_table=dynamodb_table,
        credentials_secret=credentials_secret,
        vpc_cidr=vpc_cidr,
        aws_region=ctx.obj["aws_region"],
        bootstrap_marker=bootstrap_marker,
        read_tg_arn=read_tg_arn,
        write_tg_arn=write_tg_arn,
    )

    try:
        replica_set.bootstrap()
    except MySQLBootstrapError as err:
        LOG.error("%s", err)
        sys.exit(1)
    except RuntimeError as err:
        LOG.error("Failed to acquire lock: %s", err)
        sys.exit(1)
    except ClientError as err:
        LOG.error("Failed to register with target group: %s", err)
        sys.exit(1)

    sys.exit(0)
