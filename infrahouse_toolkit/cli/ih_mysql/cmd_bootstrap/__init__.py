"""
.. topic:: ``ih-mysql bootstrap``

    Bootstrap Percona/MySQL server as master or replica.

    This command coordinates master election via DynamoDB lock,
    creates MySQL users on master, configures replication on replicas,
    and registers instances with target groups.

    See ``ih-mysql bootstrap --help`` for more details.
"""

import os
import subprocess
import sys
from logging import getLogger

import boto3
import click
from botocore.exceptions import ClientError
from infrahouse_core.aws.dynamodb import DynamoDBTable
from infrahouse_core.aws.ec2_instance import EC2Instance
from infrahouse_core.aws.exceptions import IHItemNotFound, IHSecretNotFound
from infrahouse_core.aws.secretsmanager import Secret

LOG = getLogger(__name__)

LOCK_ACQUIRE_TIMEOUT = 60  # seconds


def execute_sql(sql, check=True):
    """Execute SQL via mysql CLI."""
    try:
        result = subprocess.run(
            ["mysql", "-u", "root"],
            input=sql,
            capture_output=True,
            text=True,
            check=check,
        )
        return True, result.stdout
    except subprocess.CalledProcessError as err:
        LOG.error("SQL execution failed: %s", err.stderr)
        return False, err.stderr


def user_exists(username, host):
    """Check if a MySQL user exists."""
    sql = f"SELECT 1 FROM mysql.user WHERE user='{username}' AND host='{host}';"
    success, output = execute_sql(sql, check=False)
    return success and "1" in output


def create_user_if_not_exists(username, host, password, grants):
    """Create a MySQL user with specified grants if it doesn't exist."""
    escaped_password = password.replace("'", "''")

    if user_exists(username, host):
        LOG.info("User '%s'@'%s' already exists, updating password and grants", username, host)
        sql = f"ALTER USER '{username}'@'{host}' IDENTIFIED BY '{escaped_password}';\n"
    else:
        LOG.info("Creating user '%s'@'%s'", username, host)
        sql = f"CREATE USER '{username}'@'{host}' IDENTIFIED BY '{escaped_password}';\n"

    if grants:
        sql += f"GRANT {grants} ON *.* TO '{username}'@'{host}';\n"

    sql += "FLUSH PRIVILEGES;\n"

    success, _ = execute_sql(sql)
    if success:
        LOG.info("User '%s'@'%s' configured successfully", username, host)
    return success


def create_mysql_users(credentials: dict, vpc_cidr: str) -> bool:
    """
    Create MySQL users for replication, backup, and monitoring.

    Note: root is NOT touched as it uses socket authentication.

    :param credentials: Dictionary with keys: replication, backup, monitor.
    :param vpc_cidr: VPC CIDR for user host restrictions.
    :return: True if all users created successfully.
    """
    users = [
        {
            "username": "repl",
            "host": vpc_cidr,
            "password": credentials["replication"],
            "grants": "REPLICATION SLAVE",
        },
        {
            "username": "backup",
            "host": "localhost",
            "password": credentials["backup"],
            "grants": "RELOAD, LOCK TABLES, PROCESS, REPLICATION CLIENT, BACKUP_ADMIN",
        },
        {
            "username": "monitor",
            "host": "localhost",
            "password": credentials["monitor"],
            "grants": "PROCESS, REPLICATION CLIENT, SELECT",
        },
        {
            "username": "monitor",
            "host": vpc_cidr,
            "password": credentials["monitor"],
            "grants": "PROCESS, REPLICATION CLIENT, SELECT",
        },
    ]

    failed = False
    for user in users:
        if not create_user_if_not_exists(user["username"], user["host"], user["password"], user["grants"]):
            failed = True

    return not failed


def configure_replication(master_ip, repl_password):
    """Configure MySQL replication to the master."""
    sql = f"""
CHANGE REPLICATION SOURCE TO
    SOURCE_HOST='{master_ip}',
    SOURCE_USER='repl',
    SOURCE_PASSWORD='{repl_password}',
    SOURCE_AUTO_POSITION=1,
    SOURCE_SSL=1;
START REPLICA;
"""
    try:
        subprocess.run(
            ["mysql", "-u", "root"],
            input=sql,
            capture_output=True,
            text=True,
            check=True,
        )
        LOG.info("Replication configured successfully")
        return True
    except subprocess.CalledProcessError as err:
        LOG.error("Failed to configure replication: %s", err.stderr)
        return False


def write_marker(bootstrap_marker, content):
    """Write the bootstrap marker file."""
    marker_dir = os.path.dirname(bootstrap_marker)
    if marker_dir and not os.path.exists(marker_dir):
        os.makedirs(marker_dir, exist_ok=True)

    with open(bootstrap_marker, "w", encoding="utf-8") as fp:
        fp.write(content)


def register_with_target_group(target_group_arn: str, instance_id: str, region: str = None):
    """
    Register an instance with an ELB target group.

    :param target_group_arn: ARN of the target group.
    :param instance_id: EC2 instance ID to register.
    :param region: AWS region.
    :raises ClientError: If registration fails.
    """
    elbv2_client = boto3.client("elbv2", region_name=region)
    try:
        elbv2_client.register_targets(
            TargetGroupArn=target_group_arn,
            Targets=[{"Id": instance_id}],
        )
        LOG.info("Registered instance %s with target group %s", instance_id, target_group_arn)
    except ClientError as err:
        LOG.error("Failed to register with target group %s: %s", target_group_arn, err)
        raise


def get_credentials(credentials_secret: str, aws_region: str) -> dict:
    """
    Retrieve and validate credentials from Secrets Manager.

    :param credentials_secret: Secret name in AWS Secrets Manager.
    :param aws_region: AWS region.
    :return: Credentials dictionary.
    :raises SystemExit: If credentials cannot be retrieved or are invalid.
    """
    try:
        secret = Secret(credentials_secret, region=aws_region)
        credentials = secret.value
        if not isinstance(credentials, dict):
            LOG.error("Credentials secret must be a JSON object")
            sys.exit(1)
    except IHSecretNotFound as err:
        LOG.error("Failed to get credentials: %s", err)
        sys.exit(1)

    required_keys = ["replication", "backup", "monitor"]
    missing_keys = [key for key in required_keys if key not in credentials]
    if missing_keys:
        LOG.error("Missing required keys in credentials: %s", ", ".join(missing_keys))
        sys.exit(1)

    return credentials


def bootstrap_as_master(
    table: DynamoDBTable,
    master_key: str,
    instance_id: str,
    credentials: dict,
    vpc_cidr: str,
    bootstrap_marker: str,
):  # pylint: disable=too-many-arguments
    """Bootstrap this instance as the master node."""
    LOG.info("No master found, becoming master")

    LOG.info("Creating MySQL users")
    if not create_mysql_users(credentials, vpc_cidr):
        LOG.error("Failed to create MySQL users")
        sys.exit(1)

    table.put_item(Item={"pk": master_key, "instance_id": instance_id})
    write_marker(bootstrap_marker, "master\n")
    LOG.info("Registered as master, marker written to %s", bootstrap_marker)


def bootstrap_as_replica(master_instance_id: str, credentials_secret: str, aws_region: str, bootstrap_marker: str):
    """Bootstrap this instance as a replica node."""
    LOG.info("Master exists: %s, configuring as replica", master_instance_id)

    master_instance = EC2Instance(instance_id=master_instance_id, region=aws_region)
    master_ip = master_instance.private_ip

    if not master_ip:
        LOG.error("Failed to get master IP for instance %s", master_instance_id)
        sys.exit(1)

    LOG.info("Master IP: %s", master_ip)

    try:
        secret = Secret(credentials_secret, region=aws_region)
        credentials = secret.value
        if not isinstance(credentials, dict):
            LOG.error("Credentials secret must be a JSON object")
            sys.exit(1)
        repl_password = credentials.get("replication")
        if not repl_password:
            LOG.error("No 'replication' key found in credentials secret")
            sys.exit(1)
    except IHSecretNotFound as err:
        LOG.error("Failed to get replication password: %s", err)
        sys.exit(1)

    if not configure_replication(master_ip, repl_password):
        sys.exit(1)

    write_marker(bootstrap_marker, f"replica:{master_ip}\n")
    LOG.info("Configured as replica, marker written to %s", bootstrap_marker)


def register_target_groups(instance_id: str, aws_region: str, read_tg_arn: str, write_tg_arn: str, is_master: bool):
    """
    Register instance with target groups.

    :raises ClientError: If registration fails.
    """
    if read_tg_arn:
        register_with_target_group(read_tg_arn, instance_id, aws_region)

    if write_tg_arn and is_master:
        register_with_target_group(write_tg_arn, instance_id, aws_region)


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
):  # pylint: disable=too-many-arguments,too-many-locals
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
    aws_region = ctx.obj["aws_region"]
    is_master = False

    if os.path.exists(bootstrap_marker):
        LOG.info("Bootstrap marker exists at %s, skipping bootstrap", bootstrap_marker)
        sys.exit(0)

    instance_id = EC2Instance().instance_id
    LOG.info("Instance ID: %s", instance_id)

    table = DynamoDBTable(dynamodb_table, region=aws_region)
    lock_name = f"{cluster_id}-bootstrap-lock"
    master_key = f"{cluster_id}-master"

    LOG.info("Attempting to acquire lock: %s", lock_name)

    try:
        with table.lock(lock_name, timeout=LOCK_ACQUIRE_TIMEOUT, key_name="pk"):
            LOG.info("Checking for existing master")

            try:
                master_item = table.get_item(Key={"pk": master_key})
                master_instance_id = master_item.get("instance_id")
            except IHItemNotFound:
                master_instance_id = None

            if master_instance_id is None:
                is_master = True
                credentials = get_credentials(credentials_secret, aws_region)
                bootstrap_as_master(table, master_key, instance_id, credentials, vpc_cidr, bootstrap_marker)
            else:
                bootstrap_as_replica(master_instance_id, credentials_secret, aws_region, bootstrap_marker)

    except RuntimeError as err:
        LOG.error("Failed to acquire lock: %s", err)
        sys.exit(1)

    try:
        register_target_groups(instance_id, aws_region, read_tg_arn, write_tg_arn, is_master)
    except ClientError as err:
        LOG.error("Failed to register with target group: %s", err)
        sys.exit(1)

    sys.exit(0)
