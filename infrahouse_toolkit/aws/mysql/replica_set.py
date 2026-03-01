"""
MySQL/Percona replica-set orchestration via DynamoDB.

Provides :class:`MySQLReplicaSet` to coordinate master election and
replica bootstrap using a DynamoDB distributed lock.
"""

import os
from logging import getLogger
from typing import List, Optional

from infrahouse_core.aws.asg_instance import ASGInstance
from infrahouse_core.aws.dynamodb import DynamoDBTable
from infrahouse_core.aws.ec2_instance import EC2Instance
from infrahouse_core.aws.exceptions import IHItemNotFound

from infrahouse_toolkit.aws.asg import ASG
from infrahouse_toolkit.aws.mysql.exceptions import MySQLBootstrapError
from infrahouse_toolkit.aws.mysql.instance import MySQLInstance

LOG = getLogger(__name__)


class MySQLReplicaSet:  # pylint: disable=too-many-instance-attributes
    """
    Orchestrates MySQL/Percona cluster bootstrap via DynamoDB coordination.

    The first instance to acquire the distributed lock becomes the master;
    subsequent instances become replicas.

    :param cluster_id: Unique identifier for the Percona cluster.
    :type cluster_id: str
    :param dynamodb_table: DynamoDB table name for distributed locking.
    :type dynamodb_table: str
    :param credentials_secret: AWS Secrets Manager secret name containing MySQL credentials.
    :type credentials_secret: str
    :param vpc_cidr: VPC CIDR for MySQL user host restrictions.
    :type vpc_cidr: str
    :param aws_region: AWS region.
    :type aws_region: str
    :param bootstrap_marker: Path to the marker file indicating bootstrap completed.
    :type bootstrap_marker: str
    :param read_tg_arn: ARN of the read target group, or ``None``.
    :type read_tg_arn: Optional[str]
    :param write_tg_arn: ARN of the write target group, or ``None``.
    :type write_tg_arn: Optional[str]
    """

    LOCK_ACQUIRE_TIMEOUT = 60  # seconds

    def __init__(  # pylint: disable=too-many-arguments
        self,
        cluster_id: str,
        dynamodb_table: str,
        credentials_secret: str,
        vpc_cidr: str,
        aws_region: str,
        bootstrap_marker: str = "/var/lib/mysql/.bootstrapped",
        read_tg_arn: Optional[str] = None,
        write_tg_arn: Optional[str] = None,
    ) -> None:
        self._cluster_id = cluster_id
        self._dynamodb_table = dynamodb_table
        self._credentials_secret = credentials_secret
        self._vpc_cidr = vpc_cidr
        self._aws_region = aws_region
        self._bootstrap_marker = bootstrap_marker
        self._read_tg_arn = read_tg_arn
        self._write_tg_arn = write_tg_arn
        self._table_instance: Optional[DynamoDBTable] = None

    # --- Public properties (alphabetical) ---

    @property
    def instances(self) -> List[MySQLInstance]:
        """
        All MySQL instances in this replica set.

        Discovers EC2 instances via the Auto Scaling group named
        after the cluster ID.

        :return: List of all MySQL instances in the cluster.
        :rtype: List[MySQLInstance]
        """
        asg = ASG(self._cluster_id)
        return [
            MySQLInstance(
                EC2Instance(instance_id=i.instance_id, region=self._aws_region),
                cluster_id=self._cluster_id,
                credentials_secret=self._credentials_secret,
                vpc_cidr=self._vpc_cidr,
                aws_region=self._aws_region,
            )
            for i in asg.instances
        ]

    @property
    def master(self) -> Optional[MySQLInstance]:
        """
        The current master instance, or ``None`` if no master is tagged.

        :return: The master MySQL instance.
        :rtype: Optional[MySQLInstance]
        """
        for instance in self._instances_by_role("master"):
            return instance
        return None

    @property
    def replicas(self) -> List[MySQLInstance]:
        """
        All replica instances in this replica set.

        :return: List of replica MySQL instances.
        :rtype: List[MySQLInstance]
        """
        return self._instances_by_role("replica")

    # --- Public methods (alphabetical) ---

    def bootstrap(self) -> None:
        """
        Run the full bootstrap sequence for this EC2 instance.

        1. Check for existing marker file (skip if present).
        2. Acquire the DynamoDB distributed lock.
        3. Determine role (master or replica).
        4. Perform role-specific bootstrap.
        5. Tag the EC2 instance with ``mysql_role``.
        6. Register with ELB target groups.
        7. Enable scale-in protection for the master.

        :raises MySQLBootstrapError: If any step fails.
        :raises RuntimeError: If the distributed lock cannot be acquired.
        :raises ClientError: If target group registration fails.
        """
        if os.path.exists(self._bootstrap_marker):
            LOG.info("Bootstrap marker exists at %s, skipping bootstrap", self._bootstrap_marker)
            return

        ec2 = EC2Instance(region=self._aws_region)
        mysql_instance = MySQLInstance(
            ec2,
            cluster_id=self._cluster_id,
            credentials_secret=self._credentials_secret,
            vpc_cidr=self._vpc_cidr,
            aws_region=self._aws_region,
        )
        LOG.info("Instance ID: %s", mysql_instance.instance_id)

        is_master = False

        LOG.info("Attempting to acquire lock: %s", self._lock_name)
        with self._table.lock(self._lock_name, timeout=self.LOCK_ACQUIRE_TIMEOUT, key_name="pk"):
            LOG.info("Checking for existing master")
            master_instance_id = self.get_master_instance_id()

            if master_instance_id is None:
                is_master = True
                self._bootstrap_as_master(mysql_instance)
            else:
                self._bootstrap_as_replica(mysql_instance, master_instance_id)

        role = "master" if is_master else "replica"
        mysql_instance.tag_role(role)
        mysql_instance.register_target_groups(self._aws_region, self._read_tg_arn, self._write_tg_arn, is_master)

        if is_master:
            asg_instance = ASGInstance(instance_id=mysql_instance.instance_id)
            asg_instance.protect()
            LOG.info("Scale-in protection enabled for master %s", mysql_instance.instance_id)

        mysql_instance.write_marker(self._bootstrap_marker, f"{role}\n")
        LOG.info("Bootstrap complete, marker written to %s", self._bootstrap_marker)

    def get_master_instance_id(self) -> Optional[str]:
        """
        Look up the current master instance ID from DynamoDB.

        :return: Master instance ID, or ``None`` if no master is registered.
        :rtype: Optional[str]
        """
        try:
            item = self._table.get_item(Key={"pk": self._master_key})
            return item.get("instance_id")
        except IHItemNotFound:
            return None

    def register_master(self, instance_id: str) -> None:
        """
        Register an instance as master in DynamoDB.

        :param instance_id: EC2 instance ID to register as master.
        :type instance_id: str
        """
        self._table.put_item(Item={"pk": self._master_key, "instance_id": instance_id})

    # --- Private properties (alphabetical) ---

    @property
    def _lock_name(self) -> str:
        """
        :return: The DynamoDB lock name for this cluster.
        :rtype: str
        """
        return f"{self._cluster_id}-bootstrap-lock"

    @property
    def _master_key(self) -> str:
        """
        :return: The DynamoDB key that stores the master instance ID.
        :rtype: str
        """
        return f"{self._cluster_id}-master"

    @property
    def _table(self) -> DynamoDBTable:
        """
        Lazy-initialise the DynamoDB table wrapper.

        :return: DynamoDBTable instance.
        :rtype: DynamoDBTable
        """
        if self._table_instance is None:
            self._table_instance = DynamoDBTable(self._dynamodb_table, region=self._aws_region)
        return self._table_instance

    # --- Private methods (alphabetical) ---

    def _bootstrap_as_master(self, mysql_instance: MySQLInstance) -> None:
        """
        Bootstrap the given instance as the master node.

        Creates MySQL users and registers the master in DynamoDB.

        :param mysql_instance: The local MySQL instance.
        :type mysql_instance: MySQLInstance
        :raises MySQLBootstrapError: If user creation fails.
        """
        LOG.info("No master found, becoming master")

        LOG.info("Creating MySQL users")
        mysql_instance.create_mysql_users()

        if mysql_instance.s3_bucket:
            LOG.info("Taking xtrabackup and streaming to s3://%s/%s/", mysql_instance.s3_bucket, self._cluster_id)
            mysql_instance.backup_to_s3()
        else:
            LOG.info("No percona:s3_bucket tag found, skipping backup")

        self.register_master(mysql_instance.instance_id)
        LOG.info("Registered as master")

    def _bootstrap_as_replica(self, mysql_instance: MySQLInstance, master_instance_id: str) -> None:
        """
        Bootstrap the given instance as a replica node.

        Configures replication to the existing master.

        :param mysql_instance: The local MySQL instance.
        :type mysql_instance: MySQLInstance
        :param master_instance_id: EC2 instance ID of the master.
        :type master_instance_id: str
        :raises MySQLBootstrapError: If replication configuration fails.
        """
        LOG.info("Master exists: %s, configuring as replica", master_instance_id)

        master_ec2 = EC2Instance(instance_id=master_instance_id, region=self._aws_region)
        master_ip = master_ec2.private_ip

        if not master_ip:
            raise MySQLBootstrapError(f"Failed to get master IP for instance {master_instance_id}")

        LOG.info("Master IP: %s", master_ip)

        if mysql_instance.s3_bucket:
            LOG.info("Restoring from backup at s3://%s/%s/", mysql_instance.s3_bucket, self._cluster_id)
            mysql_instance.restore_from_s3()
        else:
            LOG.info("No percona:s3_bucket tag found, skipping restore")

        mysql_instance.configure_replication(master_ip)
        mysql_instance.wait_for_replication_sync()
        LOG.info("Configured as replica of %s, replication caught up", master_ip)

    def _instances_by_role(self, role: str) -> List[MySQLInstance]:
        """
        Filter cluster instances by their ``mysql_role`` tag.

        :param role: Role to filter by (e.g. ``"master"`` or ``"replica"``).
        :type role: str
        :return: Instances matching the role.
        :rtype: List[MySQLInstance]
        """
        return [i for i in self.instances if i.tags.get("mysql_role") == role]
