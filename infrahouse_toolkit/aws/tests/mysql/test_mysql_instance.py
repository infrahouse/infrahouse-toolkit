"""Tests for :class:`infrahouse_toolkit.aws.mysql.MySQLInstance`."""

import base64
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from botocore.exceptions import ClientError
from infrahouse_core.aws.exceptions import IHSecretNotFound

from infrahouse_toolkit.aws.mysql import MySQLBootstrapError, MySQLInstance

MOCK_CREDENTIALS = {"replication": "rpass", "backup": "bpass", "monitor": "mpass"}


@pytest.fixture()
def mock_ec2() -> MagicMock:
    """Return a mock EC2Instance."""
    ec2 = MagicMock()
    ec2.instance_id = "i-1234567890abcdef0"
    ec2.private_ip = "10.0.1.5"
    ec2.tags = {}
    return ec2


@pytest.fixture()
def mysql_instance(mock_ec2: MagicMock) -> MySQLInstance:
    """Return a MySQLInstance with a mocked EC2Instance."""
    return MySQLInstance(
        mock_ec2,
        cluster_id="my-cluster",
        credentials_secret="test-secret",
        vpc_cidr="10.0.0.0/16",
        aws_region="us-east-1",
    )


def test_instance_id(mysql_instance: MySQLInstance) -> None:
    """instance_id delegates to EC2Instance."""
    assert mysql_instance.instance_id == "i-1234567890abcdef0"


def test_private_ip(mysql_instance: MySQLInstance) -> None:
    """private_ip delegates to EC2Instance."""
    assert mysql_instance.private_ip == "10.0.1.5"


def test_s3_bucket(mysql_instance: MySQLInstance, mock_ec2: MagicMock) -> None:
    """s3_bucket returns the percona:s3_bucket tag value."""
    mock_ec2.tags = {"percona:s3_bucket": "my-bucket"}
    assert mysql_instance.s3_bucket == "my-bucket"


def test_s3_bucket_absent(mysql_instance: MySQLInstance, mock_ec2: MagicMock) -> None:
    """s3_bucket returns None when tag is absent."""
    mock_ec2.tags = {}
    assert mysql_instance.s3_bucket is None


class TestCredentials:
    """Tests for MySQLInstance.credentials property."""

    @patch("infrahouse_toolkit.aws.mysql.instance.Secret")
    def test_valid_credentials(self, mock_secret_cls: MagicMock, mysql_instance: MySQLInstance) -> None:
        """Returns credentials when secret is valid."""
        mock_secret_cls.return_value.value = {"replication": "r", "backup": "b", "monitor": "m"}
        creds = mysql_instance.credentials
        assert creds == {"replication": "r", "backup": "b", "monitor": "m"}

    @patch("infrahouse_toolkit.aws.mysql.instance.Secret")
    def test_secret_not_found(self, mock_secret_cls: MagicMock, mysql_instance: MySQLInstance) -> None:
        """Raises MySQLBootstrapError when secret does not exist."""
        mock_secret_cls.side_effect = IHSecretNotFound("not found")
        with pytest.raises(MySQLBootstrapError, match="Failed to get credentials"):
            _ = mysql_instance.credentials

    @patch("infrahouse_toolkit.aws.mysql.instance.Secret")
    def test_not_a_dict(self, mock_secret_cls: MagicMock, mysql_instance: MySQLInstance) -> None:
        """Raises MySQLBootstrapError when secret value is not a dict."""
        mock_secret_cls.return_value.value = "plaintext"
        with pytest.raises(MySQLBootstrapError, match="must be a JSON object"):
            _ = mysql_instance.credentials

    @patch("infrahouse_toolkit.aws.mysql.instance.Secret")
    def test_missing_keys(self, mock_secret_cls: MagicMock, mysql_instance: MySQLInstance) -> None:
        """Raises MySQLBootstrapError when required keys are missing."""
        mock_secret_cls.return_value.value = {"replication": "r"}
        with pytest.raises(MySQLBootstrapError, match="Missing required keys"):
            _ = mysql_instance.credentials

    @patch("infrahouse_toolkit.aws.mysql.instance.Secret")
    def test_cached(self, mock_secret_cls: MagicMock, mysql_instance: MySQLInstance) -> None:
        """Credentials are fetched only once and cached."""
        mock_secret_cls.return_value.value = {"replication": "r", "backup": "b", "monitor": "m"}
        _ = mysql_instance.credentials
        _ = mysql_instance.credentials
        mock_secret_cls.assert_called_once()


class TestExecuteSQL:
    """Tests for MySQLInstance.execute_sql."""

    def test_success(self, mysql_instance: MySQLInstance, mock_ec2: MagicMock) -> None:
        """Successful SQL execution returns stdout via base64 temp file."""
        mock_ec2.execute_command.return_value = (0, "OK\n", "")
        output = mysql_instance.execute_sql("SELECT 1;")
        assert output == "OK\n"
        mock_ec2.execute_command.assert_called_once()
        command_arg = mock_ec2.execute_command.call_args[0][0]
        encoded = base64.b64encode(b"SELECT 1;").decode("ascii")
        assert encoded in command_arg
        assert "mktemp" in command_arg
        assert "sudo mysql -u root" in command_arg
        assert 'rm -f "$tmpfile"' in command_arg

    def test_failure_raises(self, mysql_instance: MySQLInstance, mock_ec2: MagicMock) -> None:
        """Failed SQL execution raises MySQLBootstrapError."""
        mock_ec2.execute_command.return_value = (1, "", "ERROR 1045")
        with pytest.raises(MySQLBootstrapError, match="ERROR 1045"):
            mysql_instance.execute_sql("BAD SQL;")


class TestBackupToS3:
    """Tests for MySQLInstance.backup_to_s3."""

    @patch.object(MySQLInstance, "_update_latest_pointer")
    @patch.object(MySQLInstance, "credentials", new_callable=PropertyMock, return_value=MOCK_CREDENTIALS)
    def test_success(
        self, mock_creds: MagicMock, mock_pointer: MagicMock, mysql_instance: MySQLInstance, mock_ec2: MagicMock
    ) -> None:
        """Builds correct xtrabackup command with password in temp .cnf."""
        mock_ec2.tags = {"percona:s3_bucket": "my-bucket"}
        mock_ec2.execute_command.return_value = (0, "", "")
        key = mysql_instance.backup_to_s3()
        mock_ec2.execute_command.assert_called_once()
        command_arg = mock_ec2.execute_command.call_args[0][0]
        assert "xtrabackup --defaults-extra-file=" in command_arg
        assert "--backup --stream=xbstream" in command_arg
        assert "s3://my-bucket/" in command_arg
        assert ".xbstream.gz" in command_arg
        assert "defaults-extra-file" in command_arg
        assert "mktemp" in command_arg
        assert "pipefail" in command_arg
        # Password must NOT appear in the command — only base64-encoded
        assert "bpass" not in command_arg
        encoded = base64.b64encode(b"[xtrabackup]\nuser=backup\npassword=bpass\n").decode("ascii")
        assert encoded in command_arg
        # Verify it updates the latest pointer
        mock_pointer.assert_called_once_with(key)

    @patch.object(MySQLInstance, "_update_latest_pointer")
    @patch.object(MySQLInstance, "credentials", new_callable=PropertyMock, return_value=MOCK_CREDENTIALS)
    def test_returns_timestamped_key(
        self, mock_creds: MagicMock, mock_pointer: MagicMock, mysql_instance: MySQLInstance, mock_ec2: MagicMock
    ) -> None:
        """Returns a timestamped S3 key by default."""
        mock_ec2.tags = {"percona:s3_bucket": "my-bucket"}
        mock_ec2.execute_command.return_value = (0, "", "")
        key = mysql_instance.backup_to_s3()
        assert key.startswith("my-cluster/")
        assert key.endswith(".xbstream.gz")
        # Timestamp part between cluster_id/ and .xbstream.gz
        assert "T" in key  # ISO timestamp

    @patch.object(MySQLInstance, "_update_latest_pointer")
    @patch.object(MySQLInstance, "credentials", new_callable=PropertyMock, return_value=MOCK_CREDENTIALS)
    def test_explicit_key(
        self, mock_creds: MagicMock, mock_pointer: MagicMock, mysql_instance: MySQLInstance, mock_ec2: MagicMock
    ) -> None:
        """Uses caller-provided backup_key."""
        mock_ec2.tags = {"percona:s3_bucket": "my-bucket"}
        mock_ec2.execute_command.return_value = (0, "", "")
        key = mysql_instance.backup_to_s3(backup_key="my-cluster/custom.xbstream.gz")
        assert key == "my-cluster/custom.xbstream.gz"
        command_arg = mock_ec2.execute_command.call_args[0][0]
        assert "s3://my-bucket/my-cluster/custom.xbstream.gz" in command_arg

    @patch.object(MySQLInstance, "credentials", new_callable=PropertyMock, return_value=MOCK_CREDENTIALS)
    def test_failure_raises(self, mock_creds: MagicMock, mysql_instance: MySQLInstance, mock_ec2: MagicMock) -> None:
        """Raises MySQLBootstrapError when backup fails."""
        mock_ec2.tags = {"percona:s3_bucket": "bucket"}
        mock_ec2.execute_command.return_value = (1, "", "xtrabackup: error")
        with pytest.raises(MySQLBootstrapError, match="Backup to S3 failed"):
            mysql_instance.backup_to_s3()

    @patch.object(MySQLInstance, "_update_latest_pointer")
    @patch.object(MySQLInstance, "credentials", new_callable=PropertyMock, return_value=MOCK_CREDENTIALS)
    def test_custom_timeout(
        self, mock_creds: MagicMock, mock_pointer: MagicMock, mysql_instance: MySQLInstance, mock_ec2: MagicMock
    ) -> None:
        """Passes custom execution_timeout to execute_command."""
        mock_ec2.tags = {"percona:s3_bucket": "bucket"}
        mock_ec2.execute_command.return_value = (0, "", "")
        mysql_instance.backup_to_s3(execution_timeout=7200)
        assert mock_ec2.execute_command.call_args[1]["execution_timeout"] == 7200


class TestRestoreFromS3:
    """Tests for MySQLInstance.restore_from_s3."""

    LATEST_KEY = "my-cluster/2026-02-28T12:00:00.xbstream.gz"

    @patch.object(MySQLInstance, "_read_latest_pointer", return_value=LATEST_KEY)
    @patch.object(MySQLInstance, "_estimate_restore_timeout", return_value=3600)
    def test_success(
        self, mock_estimate: MagicMock, mock_pointer: MagicMock, mysql_instance: MySQLInstance, mock_ec2: MagicMock
    ) -> None:
        """Reads latest pointer and restores from that key."""
        mock_ec2.tags = {"percona:s3_bucket": "my-bucket"}
        mock_ec2.execute_command.return_value = (0, "", "")
        mysql_instance.restore_from_s3()
        mock_pointer.assert_called_once()
        mock_ec2.execute_command.assert_called_once()
        command_arg = mock_ec2.execute_command.call_args[0][0]
        assert "systemctl stop mysql" in command_arg
        assert "rm -rf /var/lib/mysql/*" in command_arg
        assert f"s3://my-bucket/{self.LATEST_KEY}" in command_arg
        assert "gunzip" in command_arg
        assert "xbstream -x -C /var/lib/mysql" in command_arg
        assert "xtrabackup --prepare --target-dir=/var/lib/mysql" in command_arg
        assert "chown -R mysql:mysql /var/lib/mysql" in command_arg
        assert "systemctl start mysql" in command_arg

    @patch.object(MySQLInstance, "_estimate_restore_timeout", return_value=3600)
    def test_explicit_key(self, mock_estimate: MagicMock, mysql_instance: MySQLInstance, mock_ec2: MagicMock) -> None:
        """Uses caller-provided backup_key without reading pointer."""
        mock_ec2.tags = {"percona:s3_bucket": "my-bucket"}
        mock_ec2.execute_command.return_value = (0, "", "")
        mysql_instance.restore_from_s3(backup_key="my-cluster/2026-01-01T00:00:00.xbstream.gz")
        command_arg = mock_ec2.execute_command.call_args[0][0]
        assert "s3://my-bucket/my-cluster/2026-01-01T00:00:00.xbstream.gz" in command_arg

    @patch.object(MySQLInstance, "_read_latest_pointer", return_value=LATEST_KEY)
    @patch.object(MySQLInstance, "_estimate_restore_timeout", return_value=3600)
    def test_failure_raises(
        self, mock_estimate: MagicMock, mock_pointer: MagicMock, mysql_instance: MySQLInstance, mock_ec2: MagicMock
    ) -> None:
        """Raises MySQLBootstrapError when restore fails."""
        mock_ec2.tags = {"percona:s3_bucket": "bucket"}
        mock_ec2.execute_command.return_value = (1, "", "restore error")
        with pytest.raises(MySQLBootstrapError, match="Restore from S3 failed"):
            mysql_instance.restore_from_s3()

    @patch.object(MySQLInstance, "_read_latest_pointer", return_value=LATEST_KEY)
    def test_explicit_timeout(
        self, mock_pointer: MagicMock, mysql_instance: MySQLInstance, mock_ec2: MagicMock
    ) -> None:
        """Uses caller-provided execution_timeout without estimating."""
        mock_ec2.tags = {"percona:s3_bucket": "bucket"}
        mock_ec2.execute_command.return_value = (0, "", "")
        mysql_instance.restore_from_s3(execution_timeout=7200)
        assert mock_ec2.execute_command.call_args[1]["execution_timeout"] == 7200

    @patch.object(MySQLInstance, "_read_latest_pointer", return_value=LATEST_KEY)
    @patch.object(MySQLInstance, "_estimate_restore_timeout", return_value=5400)
    def test_estimates_timeout_when_not_provided(
        self, mock_estimate: MagicMock, mock_pointer: MagicMock, mysql_instance: MySQLInstance, mock_ec2: MagicMock
    ) -> None:
        """Calls _estimate_restore_timeout with the resolved key."""
        mock_ec2.tags = {"percona:s3_bucket": "my-bucket"}
        mock_ec2.execute_command.return_value = (0, "", "")
        mysql_instance.restore_from_s3()
        mock_estimate.assert_called_once_with("my-bucket", self.LATEST_KEY)
        assert mock_ec2.execute_command.call_args[1]["execution_timeout"] == 5400


class TestEstimateRestoreTimeout:
    """Tests for MySQLInstance._estimate_restore_timeout."""

    @patch("infrahouse_toolkit.aws.mysql.instance.boto3")
    def test_estimates_from_size(self, mock_boto3: MagicMock, mysql_instance: MySQLInstance) -> None:
        """Estimates timeout based on S3 object size."""
        # 100 GB compressed -> 100*1024^3 / (50*1024^2) = 2048s download
        # 2048 * 2 (prepare multiplier) = 4096s
        size_bytes = 100 * 1024**3
        mock_boto3.client.return_value.head_object.return_value = {"ContentLength": size_bytes}
        timeout = mysql_instance._estimate_restore_timeout("bucket", "key")
        assert timeout == 4096

    @patch("infrahouse_toolkit.aws.mysql.instance.boto3")
    def test_minimum_timeout(self, mock_boto3: MagicMock, mysql_instance: MySQLInstance) -> None:
        """Returns minimum 3600s for small backups."""
        mock_boto3.client.return_value.head_object.return_value = {"ContentLength": 1024}
        timeout = mysql_instance._estimate_restore_timeout("bucket", "key")
        assert timeout == 3600

    @patch("infrahouse_toolkit.aws.mysql.instance.boto3")
    def test_raises_on_error(self, mock_boto3: MagicMock, mysql_instance: MySQLInstance) -> None:
        """Raises MySQLBootstrapError when HEAD fails."""
        mock_boto3.client.return_value.head_object.side_effect = ClientError(
            {"Error": {"Code": "404", "Message": "Not Found"}}, "HeadObject"
        )
        with pytest.raises(MySQLBootstrapError, match="Cannot access backup"):
            mysql_instance._estimate_restore_timeout("bucket", "key")


class TestUserExists:
    """Tests for MySQLInstance.user_exists."""

    @patch.object(MySQLInstance, "execute_sql")
    def test_user_found(self, mock_sql: MagicMock, mysql_instance: MySQLInstance) -> None:
        """Returns True when the user exists."""
        mock_sql.return_value = "1\n"
        assert mysql_instance.user_exists("repl", "10.0.0.0/16") is True

    @patch.object(MySQLInstance, "execute_sql")
    def test_user_not_found(self, mock_sql: MagicMock, mysql_instance: MySQLInstance) -> None:
        """Returns False when the user does not exist."""
        mock_sql.return_value = ""
        assert mysql_instance.user_exists("repl", "10.0.0.0/16") is False

    @patch.object(MySQLInstance, "execute_sql")
    def test_sql_failure_raises(self, mock_sql: MagicMock, mysql_instance: MySQLInstance) -> None:
        """Raises MySQLBootstrapError when SQL execution fails."""
        mock_sql.side_effect = MySQLBootstrapError("SQL execution failed")
        with pytest.raises(MySQLBootstrapError):
            mysql_instance.user_exists("repl", "10.0.0.0/16")


class TestCreateUserIfNotExists:
    """Tests for MySQLInstance.create_user_if_not_exists."""

    @patch.object(MySQLInstance, "execute_sql")
    @patch.object(MySQLInstance, "user_exists", return_value=False)
    def test_creates_new_user(self, mock_exists: MagicMock, mock_sql: MagicMock, mysql_instance: MySQLInstance) -> None:
        """Creates a new user when it does not exist."""
        mock_sql.return_value = ""
        mysql_instance.create_user_if_not_exists("repl", "10.0.0.0/16", "secret", "REPLICATION SLAVE")
        sql_arg = mock_sql.call_args[0][0]
        assert "CREATE USER" in sql_arg
        assert "GRANT REPLICATION SLAVE" in sql_arg

    @patch.object(MySQLInstance, "execute_sql")
    @patch.object(MySQLInstance, "user_exists", return_value=True)
    def test_updates_existing_user(
        self, mock_exists: MagicMock, mock_sql: MagicMock, mysql_instance: MySQLInstance
    ) -> None:
        """Updates password when user already exists."""
        mock_sql.return_value = ""
        mysql_instance.create_user_if_not_exists("repl", "10.0.0.0/16", "secret", "REPLICATION SLAVE")
        sql_arg = mock_sql.call_args[0][0]
        assert "ALTER USER" in sql_arg

    @patch.object(MySQLInstance, "execute_sql")
    @patch.object(MySQLInstance, "user_exists", return_value=False)
    def test_escapes_password(self, mock_exists: MagicMock, mock_sql: MagicMock, mysql_instance: MySQLInstance) -> None:
        """Special characters in password are escaped via pymysql escape_string."""
        mock_sql.return_value = ""
        mysql_instance.create_user_if_not_exists("repl", "localhost", "p'ass", "REPLICATION SLAVE")
        sql_arg = mock_sql.call_args[0][0]
        assert "p\\'ass" in sql_arg

    @patch.object(MySQLInstance, "execute_sql")
    @patch.object(MySQLInstance, "user_exists", return_value=False)
    def test_failure_raises(self, mock_exists: MagicMock, mock_sql: MagicMock, mysql_instance: MySQLInstance) -> None:
        """Raises MySQLBootstrapError when SQL fails."""
        mock_sql.side_effect = MySQLBootstrapError("SQL execution failed")
        with pytest.raises(MySQLBootstrapError):
            mysql_instance.create_user_if_not_exists("repl", "localhost", "secret", "REPLICATION SLAVE")


class TestCreateMySQLUsers:
    """Tests for MySQLInstance.create_mysql_users."""

    @patch.object(MySQLInstance, "credentials", new_callable=PropertyMock, return_value=MOCK_CREDENTIALS)
    @patch.object(MySQLInstance, "create_user_if_not_exists")
    def test_all_users_created(
        self, mock_create: MagicMock, mock_creds: MagicMock, mysql_instance: MySQLInstance
    ) -> None:
        """Calls create_user_if_not_exists for all four users."""
        mysql_instance.create_mysql_users()
        assert mock_create.call_count == 4

    @patch.object(MySQLInstance, "credentials", new_callable=PropertyMock, return_value=MOCK_CREDENTIALS)
    @patch.object(MySQLInstance, "create_user_if_not_exists")
    def test_failure_raises(self, mock_create: MagicMock, mock_creds: MagicMock, mysql_instance: MySQLInstance) -> None:
        """Raises MySQLBootstrapError when any user creation fails."""
        mock_create.side_effect = [None, MySQLBootstrapError("failed"), None, None]
        with pytest.raises(MySQLBootstrapError):
            mysql_instance.create_mysql_users()


class TestConfigureReplication:
    """Tests for MySQLInstance.configure_replication."""

    @patch.object(MySQLInstance, "credentials", new_callable=PropertyMock, return_value=MOCK_CREDENTIALS)
    @patch.object(MySQLInstance, "execute_sql")
    def test_success(self, mock_sql: MagicMock, mock_creds: MagicMock, mysql_instance: MySQLInstance) -> None:
        """Does not raise on successful replication setup."""
        mock_sql.return_value = ""
        mysql_instance.configure_replication("10.0.1.1")
        sql_arg = mock_sql.call_args[0][0]
        assert "STOP REPLICA" in sql_arg
        assert "CHANGE REPLICATION SOURCE TO" in sql_arg
        assert "SOURCE_HOST='10.0.1.1'" in sql_arg
        assert "START REPLICA" in sql_arg

    @patch.object(MySQLInstance, "credentials", new_callable=PropertyMock, return_value=MOCK_CREDENTIALS)
    @patch.object(MySQLInstance, "execute_sql")
    def test_failure_raises(self, mock_sql: MagicMock, mock_creds: MagicMock, mysql_instance: MySQLInstance) -> None:
        """Raises MySQLBootstrapError when replication setup fails."""
        mock_sql.side_effect = MySQLBootstrapError("SQL execution failed")
        with pytest.raises(MySQLBootstrapError):
            mysql_instance.configure_replication("10.0.1.1")


class TestReplicaStatusProperties:
    """Tests for replica_io_running, replica_sql_running, seconds_behind_source."""

    REPLICA_OUTPUT = (
        "*************************** 1. row ***************************\n"
        "             Replica_IO_Running: Yes\n"
        "            Replica_SQL_Running: Yes\n"
        "        Seconds_Behind_Source: 42\n"
    )

    @patch.object(MySQLInstance, "execute_sql", return_value=REPLICA_OUTPUT)
    def test_io_running_true(self, mock_sql: MagicMock, mysql_instance: MySQLInstance) -> None:
        """Returns True when Replica_IO_Running is Yes."""
        assert mysql_instance.replica_io_running is True

    @patch.object(MySQLInstance, "execute_sql", return_value=REPLICA_OUTPUT)
    def test_sql_running_true(self, mock_sql: MagicMock, mysql_instance: MySQLInstance) -> None:
        """Returns True when Replica_SQL_Running is Yes."""
        assert mysql_instance.replica_sql_running is True

    @patch.object(MySQLInstance, "execute_sql", return_value=REPLICA_OUTPUT)
    def test_seconds_behind(self, mock_sql: MagicMock, mysql_instance: MySQLInstance) -> None:
        """Returns integer lag."""
        assert mysql_instance.seconds_behind_source == 42

    @patch.object(
        MySQLInstance,
        "execute_sql",
        return_value="             Replica_IO_Running: No\n            Replica_SQL_Running: No\n",
    )
    def test_not_running(self, mock_sql: MagicMock, mysql_instance: MySQLInstance) -> None:
        """Returns False when threads are not running."""
        assert mysql_instance.replica_io_running is False
        assert mysql_instance.replica_sql_running is False

    @patch.object(MySQLInstance, "execute_sql", return_value="")
    def test_master_returns_none(self, mock_sql: MagicMock, mysql_instance: MySQLInstance) -> None:
        """Returns None on a master (empty SHOW REPLICA STATUS output)."""
        assert mysql_instance.replica_io_running is None
        assert mysql_instance.replica_sql_running is None
        assert mysql_instance.seconds_behind_source is None

    @patch.object(
        MySQLInstance,
        "execute_sql",
        return_value=(
            "             Replica_IO_Running: Yes\n"
            "            Replica_SQL_Running: Yes\n"
            "        Seconds_Behind_Source: NULL\n"
        ),
    )
    def test_seconds_behind_null(self, mock_sql: MagicMock, mysql_instance: MySQLInstance) -> None:
        """Returns None when Seconds_Behind_Source is NULL."""
        assert mysql_instance.seconds_behind_source is None


class TestWaitForReplicationSync:
    """Tests for MySQLInstance.wait_for_replication_sync."""

    @patch.object(MySQLInstance, "seconds_behind_source", new_callable=PropertyMock, return_value=0)
    @patch.object(MySQLInstance, "replica_sql_running", new_callable=PropertyMock, return_value=True)
    @patch.object(MySQLInstance, "replica_io_running", new_callable=PropertyMock, return_value=True)
    def test_returns_when_caught_up(
        self, mock_io: MagicMock, mock_sql: MagicMock, mock_lag: MagicMock, mysql_instance: MySQLInstance
    ) -> None:
        """Returns immediately when lag is below threshold."""
        mysql_instance.wait_for_replication_sync(threshold_seconds=30)

    @patch("infrahouse_toolkit.aws.mysql.instance.time.sleep")
    @patch.object(MySQLInstance, "seconds_behind_source", new_callable=PropertyMock, side_effect=[500, 10])
    @patch.object(MySQLInstance, "replica_sql_running", new_callable=PropertyMock, return_value=True)
    @patch.object(MySQLInstance, "replica_io_running", new_callable=PropertyMock, return_value=True)
    def test_polls_until_caught_up(
        self,
        mock_io: MagicMock,
        mock_sql: MagicMock,
        mock_lag: MagicMock,
        mock_sleep: MagicMock,
        mysql_instance: MySQLInstance,
    ) -> None:
        """Polls until lag drops below threshold."""
        mysql_instance.wait_for_replication_sync(threshold_seconds=30)
        mock_sleep.assert_called_once()

    @patch.object(MySQLInstance, "replica_sql_running", new_callable=PropertyMock, return_value=True)
    @patch.object(MySQLInstance, "replica_io_running", new_callable=PropertyMock, return_value=False)
    def test_raises_when_io_not_running(
        self, mock_io: MagicMock, mock_sql: MagicMock, mysql_instance: MySQLInstance
    ) -> None:
        """Raises MySQLBootstrapError when Replica_IO_Running is False."""
        with pytest.raises(MySQLBootstrapError, match="Replication is not running"):
            mysql_instance.wait_for_replication_sync()

    @patch.object(MySQLInstance, "replica_sql_running", new_callable=PropertyMock, return_value=False)
    @patch.object(MySQLInstance, "replica_io_running", new_callable=PropertyMock, return_value=True)
    def test_raises_when_sql_not_running(
        self, mock_io: MagicMock, mock_sql: MagicMock, mysql_instance: MySQLInstance
    ) -> None:
        """Raises MySQLBootstrapError when Replica_SQL_Running is False."""
        with pytest.raises(MySQLBootstrapError, match="Replication is not running"):
            mysql_instance.wait_for_replication_sync()

    @patch("infrahouse_toolkit.aws.mysql.instance.time.monotonic", side_effect=[0, 101])
    @patch("infrahouse_toolkit.aws.mysql.instance.time.sleep")
    @patch.object(MySQLInstance, "seconds_behind_source", new_callable=PropertyMock, return_value=5000)
    @patch.object(MySQLInstance, "replica_sql_running", new_callable=PropertyMock, return_value=True)
    @patch.object(MySQLInstance, "replica_io_running", new_callable=PropertyMock, return_value=True)
    def test_raises_on_timeout(
        self,
        mock_io: MagicMock,
        mock_sql: MagicMock,
        mock_lag: MagicMock,
        mock_sleep: MagicMock,
        mock_monotonic: MagicMock,
        mysql_instance: MySQLInstance,
    ) -> None:
        """Raises MySQLBootstrapError when timeout is exceeded."""
        with pytest.raises(MySQLBootstrapError, match="did not catch up"):
            mysql_instance.wait_for_replication_sync(threshold_seconds=30, timeout=100)


class TestTagRole:
    """Tests for MySQLInstance.tag_role."""

    def test_tags_master(self, mysql_instance: MySQLInstance, mock_ec2: MagicMock) -> None:
        """Tags the instance with mysql_role=master."""
        mysql_instance.tag_role("master")
        mock_ec2.add_tag.assert_called_once_with(key="mysql_role", value="master")

    def test_tags_replica(self, mysql_instance: MySQLInstance, mock_ec2: MagicMock) -> None:
        """Tags the instance with mysql_role=replica."""
        mysql_instance.tag_role("replica")
        mock_ec2.add_tag.assert_called_once_with(key="mysql_role", value="replica")


class TestRegisterTargetGroups:
    """Tests for MySQLInstance.register_target_groups."""

    @patch.object(MySQLInstance, "register_with_target_group")
    def test_master_registers_both(self, mock_reg: MagicMock, mysql_instance: MySQLInstance) -> None:
        """Master registers with both read and write target groups."""
        mysql_instance.register_target_groups("us-east-1", "arn:read", "arn:write", is_master=True)
        assert mock_reg.call_count == 2
        mock_reg.assert_any_call("arn:read", "us-east-1")
        mock_reg.assert_any_call("arn:write", "us-east-1")

    @patch.object(MySQLInstance, "register_with_target_group")
    def test_replica_registers_read_only(self, mock_reg: MagicMock, mysql_instance: MySQLInstance) -> None:
        """Replica registers only with the read target group."""
        mysql_instance.register_target_groups("us-east-1", "arn:read", "arn:write", is_master=False)
        mock_reg.assert_called_once_with("arn:read", "us-east-1")

    @patch.object(MySQLInstance, "register_with_target_group")
    def test_no_target_groups(self, mock_reg: MagicMock, mysql_instance: MySQLInstance) -> None:
        """No registration when both ARNs are None."""
        mysql_instance.register_target_groups("us-east-1", None, None, is_master=True)
        mock_reg.assert_not_called()


class TestWriteMarker:
    """Tests for MySQLInstance.write_marker."""

    def test_writes_file(self, tmp_path) -> None:
        """Writes content to the marker file."""
        marker = str(tmp_path / "marker")
        MySQLInstance.write_marker(marker, "master\n")
        with open(marker, encoding="utf-8") as f:
            assert f.read() == "master\n"

    def test_creates_directory(self, tmp_path) -> None:
        """Creates parent directories if they do not exist."""
        marker = str(tmp_path / "subdir" / "marker")
        MySQLInstance.write_marker(marker, "replica:10.0.1.1\n")
        with open(marker, encoding="utf-8") as f:
            assert f.read() == "replica:10.0.1.1\n"
