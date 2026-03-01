"""
MySQL/Percona instance running on an EC2 instance.

Provides :class:`MySQLInstance` to manage a MySQL server on an EC2 instance —
executing SQL via SSM, creating users, configuring replication, and managing
EC2 tags and ELB target group registration.
"""

import base64
import os
import re
import time
from datetime import datetime, timezone
from logging import getLogger
from typing import Dict, Optional

import boto3
from botocore.exceptions import ClientError
from cached_property import cached_property_with_ttl
from infrahouse_core.aws.ec2_instance import EC2Instance
from infrahouse_core.aws.exceptions import IHSecretNotFound
from infrahouse_core.aws.secretsmanager import Secret
from pymysql.converters import escape_string

from infrahouse_toolkit.aws.mysql.exceptions import MySQLBootstrapError

LOG = getLogger(__name__)


class MySQLInstance:
    """
    Represents a MySQL/Percona server running on an EC2 instance.

    Provides methods for executing SQL, creating users, configuring
    replication, and managing EC2 tags and ELB target group registration.

    :param ec2_instance: The EC2 instance this MySQL server runs on.
    :type ec2_instance: EC2Instance
    :param cluster_id: Cluster identifier (used as S3 key prefix for backups).
    :type cluster_id: str
    :param credentials_secret: AWS Secrets Manager secret name containing MySQL credentials.
    :type credentials_secret: str
    :param vpc_cidr: VPC CIDR for MySQL user host restrictions.
    :type vpc_cidr: str
    :param aws_region: AWS region for Secrets Manager lookups.
    :type aws_region: str
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        ec2_instance: EC2Instance,
        cluster_id: str = None,
        credentials_secret: str = None,
        vpc_cidr: str = None,
        aws_region: str = None,
    ) -> None:
        self._ec2_instance = ec2_instance
        self._cluster_id = cluster_id
        self._credentials_secret = credentials_secret
        self._vpc_cidr = vpc_cidr
        self._aws_region = aws_region
        self._credentials: Optional[Dict[str, str]] = None

    # --- Public properties (alphabetical) ---

    @property
    def credentials(self) -> Dict[str, str]:
        """
        MySQL credentials from Secrets Manager (cached after first fetch).

        :return: Credentials dictionary with keys ``replication``, ``backup``, ``monitor``.
        :rtype: Dict[str, str]
        :raises MySQLBootstrapError: If credentials cannot be retrieved or are invalid.
        """
        if self._credentials is None:
            try:
                secret = Secret(self._credentials_secret, region=self._aws_region)
                value = secret.value
                if not isinstance(value, dict):
                    raise MySQLBootstrapError("Credentials secret must be a JSON object")
            except IHSecretNotFound as err:
                raise MySQLBootstrapError(f"Failed to get credentials: {err}") from err

            required_keys = ["replication", "backup", "monitor"]
            missing_keys = [key for key in required_keys if key not in value]
            if missing_keys:
                raise MySQLBootstrapError(f"Missing required keys in credentials: {', '.join(missing_keys)}")

            self._credentials = value
        return self._credentials

    @property
    def instance_id(self) -> str:
        """
        :return: The EC2 instance ID.
        :rtype: str
        """
        return self._ec2_instance.instance_id

    @property
    def private_ip(self) -> Optional[str]:
        """
        :return: The private IP address of the EC2 instance.
        :rtype: Optional[str]
        """
        return self._ec2_instance.private_ip

    @property
    def replica_io_running(self) -> Optional[bool]:
        """
        Whether the replica I/O thread is running.

        :return: ``True``/``False`` for a replica, ``None`` on a master
            (where ``SHOW REPLICA STATUS`` returns no rows).
        :rtype: Optional[bool]
        """
        status = self._replica_status
        if not status:
            return None
        return status.get("Replica_IO_Running") == "Yes"

    @property
    def replica_sql_running(self) -> Optional[bool]:
        """
        Whether the replica SQL thread is running.

        :return: ``True``/``False`` for a replica, ``None`` on a master
            (where ``SHOW REPLICA STATUS`` returns no rows).
        :rtype: Optional[bool]
        """
        status = self._replica_status
        if not status:
            return None
        return status.get("Replica_SQL_Running") == "Yes"

    @property
    def s3_bucket(self) -> Optional[str]:
        """
        S3 bucket for xtrabackup, from the ``percona:s3_bucket`` EC2 tag.

        :return: S3 bucket name, or ``None`` if the tag is not set.
        :rtype: Optional[str]
        """
        return self.tags.get("percona:s3_bucket") or None

    @property
    def seconds_behind_source(self) -> Optional[int]:
        """
        Replication lag in seconds.

        :return: Lag in seconds for a replica, ``None`` on a master or
            when ``Seconds_Behind_Source`` is ``NULL``.
        :rtype: Optional[int]
        """
        status = self._replica_status
        if not status:
            return None
        raw = status.get("Seconds_Behind_Source")
        if raw is None or raw == "NULL":
            return None
        return int(raw)

    @property
    def tags(self) -> dict:
        """
        :return: A dictionary with the EC2 instance tags.
        :rtype: dict
        """
        return self._ec2_instance.tags

    # --- Public methods (alphabetical, backup/restore group) ---

    def backup_to_s3(self, backup_key: str = None, execution_timeout: int = 28800) -> str:
        """
        Take an xtrabackup and stream it to S3.

        Uses :attr:`s3_bucket` for the destination and :attr:`credentials`
        for the backup password.  Creates a temporary ``.cnf`` file with
        the backup credentials (0600 permissions) to avoid exposing the
        password in the process list.

        When *backup_key* is ``None`` (the default), a timestamped key is
        generated (e.g. ``cluster/2026-02-28T12:30:00.xbstream.gz``).
        After a successful upload the backup is also copied to
        ``cluster/latest.xbstream.gz``.

        :param backup_key: S3 object key, or ``None`` for a timestamped default.
        :type backup_key: str
        :param execution_timeout: Seconds to wait for backup completion.
        :type execution_timeout: int
        :return: The S3 object key of the backup.
        :rtype: str
        :raises MySQLBootstrapError: If the backup command fails.
        """
        if backup_key is None:
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
            backup_key = f"{self._cluster_id}/{timestamp}.xbstream.gz"

        backup_password = self.credentials["backup"]
        cnf_content = f"[xtrabackup]\nuser=backup\npassword={backup_password}\n"
        encoded_cnf = base64.b64encode(cnf_content.encode("utf-8")).decode("ascii")
        s3_uri = f"s3://{self.s3_bucket}/{backup_key}"
        # 1. Create a temp .cnf with 0600 permissions containing backup credentials.
        # 2. Stream xtrabackup through gzip to S3.
        # 3. pipefail ensures xtrabackup failures propagate through the pipe.
        # 4. Clean up the temp .cnf file.
        # Wrapped in bash -c because SSM runs commands with /bin/sh which lacks pipefail.
        script = (
            "set -o pipefail; "
            f'cnf=$(umask 0177 && mktemp --suffix=.cnf) && echo {encoded_cnf} | base64 -d > "$cnf" && '
            f'sudo xtrabackup --defaults-extra-file="$cnf" --backup --stream=xbstream'
            f" | gzip"
            f" | aws s3 cp - {s3_uri}; "
            'ret=$?; rm -f "$cnf"; exit "$ret"'
        )
        command = f"bash -c '{script}'"
        exit_code, _, stderr = self._ec2_instance.execute_command(command, execution_timeout=execution_timeout)
        if exit_code != 0:
            raise MySQLBootstrapError(f"Backup to S3 failed: {stderr}")
        LOG.info("Backup streamed to %s", s3_uri)

        self._update_latest_pointer(backup_key)
        return backup_key

    def restore_from_s3(self, backup_key: str = None, execution_timeout: int = None) -> None:
        """
        Stop MySQL, restore an xtrabackup from S3, and start MySQL.

        Uses :attr:`s3_bucket` for the source.  When *backup_key* is
        ``None`` (the default), reads the ``cluster/latest`` pointer
        to find the most recent backup.

        When *execution_timeout* is ``None`` (the default), the timeout is
        estimated from the compressed backup size in S3: 50 MB/s throughput
        with a 2x multiplier for the ``--prepare`` phase, minimum 3600s.

        :param backup_key: S3 object key, or ``None`` for the latest backup.
        :type backup_key: str
        :param execution_timeout: Seconds to wait for restore completion,
            or ``None`` to estimate from backup size.
        :type execution_timeout: int
        :raises MySQLBootstrapError: If the restore command fails.
        """
        if backup_key is None:
            backup_key = self._read_latest_pointer()

        if execution_timeout is None:
            execution_timeout = self._estimate_restore_timeout(self.s3_bucket, backup_key)

        s3_uri = f"s3://{self.s3_bucket}/{backup_key}"
        # Wrapped in bash -c because SSM runs commands with /bin/sh which lacks pipefail.
        script = (
            "set -o pipefail && "
            "sudo systemctl stop mysql && "
            "sudo rm -rf /var/lib/mysql/* && "
            f"aws s3 cp {s3_uri} - | gunzip | sudo xbstream -x -C /var/lib/mysql && "
            "sudo xtrabackup --prepare --target-dir=/var/lib/mysql && "
            "sudo chown -R mysql:mysql /var/lib/mysql && "
            "sudo systemctl start mysql"
        )
        command = f"bash -c '{script}'"
        exit_code, _, stderr = self._ec2_instance.execute_command(command, execution_timeout=execution_timeout)
        if exit_code != 0:
            raise MySQLBootstrapError(f"Restore from S3 failed: {stderr}")
        LOG.info("Restored from %s", s3_uri)

    # --- Public methods (alphabetical, SQL group) ---

    def configure_replication(self, master_ip: str) -> None:
        """
        Configure MySQL replication to the given master.

        Uses the ``replication`` password from :attr:`credentials`.
        Executes ``CHANGE REPLICATION SOURCE TO`` and ``START REPLICA``
        on the remote instance via SSM.

        :param master_ip: Private IP of the master instance.
        :type master_ip: str
        :raises MySQLBootstrapError: If the SQL statements fail.
        """
        esc_ip = escape_string(master_ip)
        esc_pass = escape_string(self.credentials["replication"])
        sql = (
            f"STOP REPLICA;"
            f"\nCHANGE REPLICATION SOURCE TO"
            f" SOURCE_HOST='{esc_ip}',"
            f" SOURCE_USER='repl',"
            f" SOURCE_PASSWORD='{esc_pass}',"
            f" SOURCE_AUTO_POSITION=1,"
            f" SOURCE_SSL=1;"
            f"\nSTART REPLICA;"
        )
        self.execute_sql(sql)
        LOG.info("Replication configured successfully")

    def create_mysql_users(self) -> None:
        """
        Create MySQL users for replication, backup, and monitoring.

        Uses :attr:`credentials` for passwords and the constructor's
        *vpc_cidr* for host restrictions.
        Root is NOT touched as it uses socket authentication.

        :raises MySQLBootstrapError: If any user creation fails.
        """
        credentials = self.credentials
        vpc_cidr = self._vpc_cidr
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
                "grants": "RELOAD, LOCK TABLES, PROCESS, REPLICATION CLIENT, BACKUP_ADMIN, SELECT",
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

        for user in users:
            self.create_user_if_not_exists(user["username"], user["host"], user["password"], user["grants"])

    def create_user_if_not_exists(self, username: str, host: str, password: str, grants: str) -> None:
        """
        Create a MySQL user with the specified grants, or update if it exists.

        :param username: MySQL username.
        :type username: str
        :param host: MySQL host pattern.
        :type host: str
        :param password: User password.
        :type password: str
        :param grants: MySQL GRANT string (e.g. ``"REPLICATION SLAVE"``).
        :type grants: str
        :raises MySQLBootstrapError: If the SQL statements fail.
        """
        esc_user = escape_string(username)
        esc_host = escape_string(host)
        esc_pass = escape_string(password)
        esc_grants = escape_string(grants)

        if self.user_exists(username, host):
            LOG.info("User '%s'@'%s' already exists, updating password and grants", username, host)
            sql = f"ALTER USER '{esc_user}'@'{esc_host}' IDENTIFIED BY '{esc_pass}';\n"
        else:
            LOG.info("Creating user '%s'@'%s'", username, host)
            sql = f"CREATE USER '{esc_user}'@'{esc_host}' IDENTIFIED BY '{esc_pass}';\n"

        if grants:
            sql += f"GRANT {esc_grants} ON *.* TO '{esc_user}'@'{esc_host}';\n"

        sql += "FLUSH PRIVILEGES;\n"

        self.execute_sql(sql)
        LOG.info("User '%s'@'%s' configured successfully", username, host)

    def execute_sql(self, sql: str) -> str:
        """
        Execute a SQL statement on the EC2 instance via SSM.

        The SQL is base64-encoded before being sent to the remote instance
        to prevent shell injection via heredoc delimiter collision.

        .. warning::

            This method does **not** escape the SQL string.  Callers are
            responsible for escaping any user-supplied values interpolated
            into *sql* (e.g. with :func:`pymysql.converters.escape_string`)
            to prevent SQL injection.

        :param sql: SQL statement(s) to execute.
        :type sql: str
        :return: Standard output from the command.
        :rtype: str
        :raises MySQLBootstrapError: If the command exits with a non-zero code.
        """
        encoded = base64.b64encode(sql.encode("utf-8")).decode("ascii")
        # 1. Create a temp file with 0600 permissions (umask 0177 = owner rw only)
        #    so credentials in SQL are not readable by other users.
        # 2. Decode the base64 SQL into the temp file — avoids exposing
        #    sensitive data in the process list and prevents shell injection.
        # 3. Feed the file to mysql via stdin redirection (not a pipe)
        #    so the exit code comes directly from mysql.
        # 4. Capture the exit code, clean up the temp file, and re-exit with it.
        script = (
            f'tmpfile=$(umask 0177 && mktemp) && echo {encoded} | base64 -d > "$tmpfile"'
            ' && sudo mysql -u root < "$tmpfile"; ret=$?; rm -f "$tmpfile"; exit "$ret"'
        )
        command = f"bash -c '{script}'"
        exit_code, stdout, stderr = self._ec2_instance.execute_command(command)
        if exit_code != 0:
            raise MySQLBootstrapError(f"SQL execution failed: {stderr}")
        return stdout

    # --- Public methods (alphabetical, EC2/AWS group) ---

    def register_target_groups(
        self, region: str, read_tg_arn: Optional[str], write_tg_arn: Optional[str], is_master: bool
    ) -> None:
        """
        Register this instance with the appropriate target groups.

        All instances register with the read target group.
        Only the master registers with the write target group.

        :param region: AWS region.
        :type region: str
        :param read_tg_arn: ARN of the read target group, or ``None``.
        :type read_tg_arn: Optional[str]
        :param write_tg_arn: ARN of the write target group, or ``None``.
        :type write_tg_arn: Optional[str]
        :param is_master: Whether this instance is the master.
        :type is_master: bool
        :raises ClientError: If registration fails.
        """
        if read_tg_arn:
            self.register_with_target_group(read_tg_arn, region)

        if write_tg_arn and is_master:
            self.register_with_target_group(write_tg_arn, region)

    def register_with_target_group(self, target_group_arn: str, region: str = None) -> None:
        """
        Register this instance with an ELB target group.

        :param target_group_arn: ARN of the target group.
        :type target_group_arn: str
        :param region: AWS region.
        :type region: str
        :raises ClientError: If registration fails.
        """
        elbv2_client = boto3.client("elbv2", region_name=region)
        try:
            elbv2_client.register_targets(
                TargetGroupArn=target_group_arn,
                Targets=[{"Id": self.instance_id}],
            )
            LOG.info("Registered instance %s with target group %s", self.instance_id, target_group_arn)
        except ClientError as err:
            LOG.error("Failed to register with target group %s: %s", target_group_arn, err)
            raise

    def tag_role(self, role: str) -> None:
        """
        Tag the EC2 instance with its MySQL role.

        :param role: Either ``"master"`` or ``"replica"``.
        :type role: str
        """
        LOG.info("Tagging instance %s with mysql_role=%s", self.instance_id, role)
        self._ec2_instance.add_tag(key="mysql_role", value=role)

    def user_exists(self, username: str, host: str) -> bool:
        """
        Check whether a MySQL user exists.

        :param username: MySQL username.
        :type username: str
        :param host: MySQL host pattern.
        :type host: str
        :return: ``True`` if the user exists.
        :rtype: bool
        :raises MySQLBootstrapError: If the query fails.
        """
        sql = f"SELECT 1 FROM mysql.user WHERE user='{escape_string(username)}' AND host='{escape_string(host)}';"
        output = self.execute_sql(sql)
        return "1" in output

    def wait_for_replication_sync(
        self, threshold_seconds: int = 30, timeout: int = 86400, poll_interval: int = 30
    ) -> None:
        """
        Wait until the replica has caught up with the master.

        Polls ``SHOW REPLICA STATUS\\G`` until ``Seconds_Behind_Source``
        drops to *threshold_seconds* or below.  Also verifies that both
        ``Replica_IO_Running`` and ``Replica_SQL_Running`` are ``Yes``.

        :param threshold_seconds: Maximum acceptable replication lag.
        :type threshold_seconds: int
        :param timeout: Maximum seconds to wait before giving up.
        :type timeout: int
        :param poll_interval: Seconds between polls.
        :type poll_interval: int
        :raises MySQLBootstrapError: If replication is not running or
            the timeout is exceeded.
        """
        deadline = time.monotonic() + timeout
        LOG.info(
            "Waiting for replication lag to drop below %ds (timeout %ds)",
            threshold_seconds,
            timeout,
        )

        while True:
            if not self.replica_io_running or not self.replica_sql_running:
                raise MySQLBootstrapError(
                    f"Replication is not running: "
                    f"Replica_IO_Running={self.replica_io_running}, "
                    f"Replica_SQL_Running={self.replica_sql_running}"
                )

            lag = self.seconds_behind_source
            if lag is None:
                LOG.warning("Seconds_Behind_Source is NULL, replication may not be active yet")
            else:
                LOG.info("Replication lag: %ds", lag)
                if lag <= threshold_seconds:
                    LOG.info("Replication caught up (lag %ds <= threshold %ds)", lag, threshold_seconds)
                    return

            if time.monotonic() >= deadline:
                raise MySQLBootstrapError(
                    f"Replication did not catch up within {timeout}s " f"(last Seconds_Behind_Source={lag})"
                )

            time.sleep(poll_interval)

    @staticmethod
    def write_marker(bootstrap_marker: str, content: str) -> None:
        """
        Write the bootstrap marker file.

        :param bootstrap_marker: Path to the marker file.
        :type bootstrap_marker: str
        :param content: Content to write.
        :type content: str
        """
        marker_dir = os.path.dirname(bootstrap_marker)
        if marker_dir and not os.path.exists(marker_dir):
            os.makedirs(marker_dir, exist_ok=True)

        with open(bootstrap_marker, "w", encoding="utf-8") as fp:
            fp.write(content)

    # --- Private properties ---

    @cached_property_with_ttl(ttl=1)
    def _replica_status(self) -> Dict[str, str]:
        """
        Parsed output of ``SHOW REPLICA STATUS\\G``, cached for 1 second.

        Multiple property accesses within the same polling iteration
        share a single SSM round-trip.  Returns an empty dict on a
        master (no rows).

        :return: Field-name to value mapping.
        :rtype: Dict[str, str]
        """
        output = self.execute_sql("SHOW REPLICA STATUS\\G")
        result: Dict[str, str] = {}
        for line in output.splitlines():
            match = re.match(r"\s*(\w+):\s*(.*)", line)
            if match:
                result[match.group(1)] = match.group(2).strip()
        return result

    @property
    def _s3_pointer_key(self) -> str:
        """
        :return: The S3 object key for the ``latest`` pointer.
        :rtype: str
        """
        return f"{self._cluster_id}/latest"

    # --- Private methods ---

    # 50 MB/s accounts for S3 download + gunzip + xbstream extraction.
    _RESTORE_THROUGHPUT_BPS = 50 * 1024 * 1024
    # The xtrabackup --prepare step roughly doubles the wall-clock time.
    _RESTORE_PREPARE_MULTIPLIER = 2
    _RESTORE_MIN_TIMEOUT = 3600

    def _estimate_restore_timeout(self, s3_bucket: str, s3_object_key: str) -> int:
        """
        Estimate execution timeout from the compressed backup size in S3.

        Assumes ~50 MB/s effective throughput for download + decompress +
        extract, with a 2x multiplier for the ``--prepare`` phase.
        Minimum 3600s.

        :param s3_bucket: S3 bucket name.
        :type s3_bucket: str
        :param s3_object_key: S3 object key.
        :type s3_object_key: str
        :return: Estimated timeout in seconds.
        :rtype: int
        :raises MySQLBootstrapError: If the S3 object cannot be accessed.
        """
        s3_client = boto3.client("s3")
        try:
            response = s3_client.head_object(Bucket=s3_bucket, Key=s3_object_key)
            size_bytes = response["ContentLength"]
        except ClientError as err:
            raise MySQLBootstrapError(f"Cannot access backup at s3://{s3_bucket}/{s3_object_key}: {err}") from err

        download_seconds = size_bytes / self._RESTORE_THROUGHPUT_BPS
        estimated = int(download_seconds * self._RESTORE_PREPARE_MULTIPLIER)
        timeout = max(estimated, self._RESTORE_MIN_TIMEOUT)
        LOG.info(
            "Backup size: %.1f GB, estimated restore timeout: %ds",
            size_bytes / (1024**3),
            timeout,
        )
        return timeout

    def _read_latest_pointer(self) -> str:
        """
        Read the ``latest`` pointer to find the most recent backup key.

        :return: The S3 object key of the latest backup.
        :rtype: str
        :raises MySQLBootstrapError: If the pointer cannot be read.
        """
        s3_client = boto3.client("s3")
        try:
            response = s3_client.get_object(Bucket=self.s3_bucket, Key=self._s3_pointer_key)
            backup_key = response["Body"].read().decode("utf-8").strip()
        except ClientError as err:
            raise MySQLBootstrapError(
                f"Cannot read latest pointer at s3://{self.s3_bucket}/{self._s3_pointer_key}: {err}"
            ) from err
        LOG.info("Latest pointer resolves to %s", backup_key)
        return backup_key

    def _update_latest_pointer(self, backup_key: str) -> None:
        """
        Write the ``latest`` pointer to point to the given backup key.

        :param backup_key: The S3 object key to point to.
        :type backup_key: str
        :raises MySQLBootstrapError: If the pointer cannot be written.
        """
        s3_client = boto3.client("s3")
        try:
            s3_client.put_object(Bucket=self.s3_bucket, Key=self._s3_pointer_key, Body=backup_key.encode("utf-8"))
        except ClientError as err:
            raise MySQLBootstrapError(
                f"Cannot update latest pointer at s3://{self.s3_bucket}/{self._s3_pointer_key}: {err}"
            ) from err
        LOG.info("Updated latest pointer to %s", backup_key)
