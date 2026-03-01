"""Tests for :class:`infrahouse_toolkit.aws.mysql.MySQLReplicaSet`."""

import os
from unittest.mock import MagicMock, patch

import pytest
from infrahouse_core.aws.exceptions import IHItemNotFound

from infrahouse_toolkit.aws.mysql import (
    MySQLBootstrapError,
    MySQLInstance,
    MySQLReplicaSet,
)


@pytest.fixture()
def replica_set() -> MySQLReplicaSet:
    """Return a MySQLReplicaSet with a mocked DynamoDB table."""
    rs = MySQLReplicaSet(
        cluster_id="test-cluster",
        dynamodb_table="test-table",
        credentials_secret="test-secret",
        vpc_cidr="10.0.0.0/16",
        aws_region="us-east-1",
        bootstrap_marker="/tmp/test-marker",
        read_tg_arn="arn:read",
        write_tg_arn="arn:write",
    )
    rs._table_instance = MagicMock()
    return rs


class TestGetMasterInstanceId:
    """Tests for MySQLReplicaSet.get_master_instance_id."""

    def test_master_found(self, replica_set: MySQLReplicaSet) -> None:
        """Returns instance ID when master is registered."""
        replica_set._table_instance.get_item.return_value = {"pk": "test-cluster-master", "instance_id": "i-master123"}
        assert replica_set.get_master_instance_id() == "i-master123"

    def test_no_master(self, replica_set: MySQLReplicaSet) -> None:
        """Returns None when no master is registered."""
        replica_set._table_instance.get_item.side_effect = IHItemNotFound("not found")
        assert replica_set.get_master_instance_id() is None


class TestRegisterMaster:
    """Tests for MySQLReplicaSet.register_master."""

    def test_puts_item(self, replica_set: MySQLReplicaSet) -> None:
        """Registers master instance ID in DynamoDB."""
        replica_set.register_master("i-master123")
        replica_set._table_instance.put_item.assert_called_once_with(
            Item={"pk": "test-cluster-master", "instance_id": "i-master123"}
        )


class TestBootstrap:
    """Tests for MySQLReplicaSet.bootstrap."""

    @patch("infrahouse_toolkit.aws.mysql.replica_set.EC2Instance")
    def test_skips_when_marker_exists(self, mock_ec2_cls: MagicMock, tmp_path) -> None:
        """bootstrap() returns immediately when marker file exists."""
        marker = str(tmp_path / "marker")
        with open(marker, "w", encoding="utf-8") as f:
            f.write("master\n")

        rs = MySQLReplicaSet(
            cluster_id="c",
            dynamodb_table="t",
            credentials_secret="s",
            vpc_cidr="10.0.0.0/16",
            aws_region="us-east-1",
            bootstrap_marker=marker,
        )
        rs.bootstrap()
        mock_ec2_cls.assert_not_called()

    @patch("infrahouse_toolkit.aws.mysql.replica_set.ASGInstance")
    @patch("infrahouse_toolkit.aws.mysql.replica_set.EC2Instance")
    @patch.object(MySQLReplicaSet, "get_master_instance_id", return_value=None)
    @patch.object(MySQLReplicaSet, "_bootstrap_as_master")
    def test_becomes_master(
        self,
        mock_master: MagicMock,
        mock_get_master: MagicMock,
        mock_ec2_cls: MagicMock,
        mock_asg_inst_cls: MagicMock,
        tmp_path,
    ) -> None:
        """First instance becomes master when no master exists."""
        mock_ec2 = mock_ec2_cls.return_value
        mock_ec2.instance_id = "i-new"
        marker = str(tmp_path / "marker")

        rs = MySQLReplicaSet(
            cluster_id="c",
            dynamodb_table="t",
            credentials_secret="s",
            vpc_cidr="10.0.0.0/16",
            aws_region="us-east-1",
            bootstrap_marker=marker,
        )
        rs._table_instance = MagicMock()
        rs._table_instance.lock.return_value.__enter__ = MagicMock()
        rs._table_instance.lock.return_value.__exit__ = MagicMock(return_value=False)

        rs.bootstrap()

        mock_master.assert_called_once()
        # Verify the EC2 instance was tagged with mysql_role=master
        mock_ec2.add_tag.assert_called_once_with(key="mysql_role", value="master")
        # Verify scale-in protection was enabled
        mock_asg_inst_cls.assert_called_once_with(instance_id="i-new")
        mock_asg_inst_cls.return_value.protect.assert_called_once()
        # Marker is written as the very last step
        assert os.path.exists(marker)
        with open(marker, encoding="utf-8") as fh:
            assert fh.read() == "master\n"

    @patch("infrahouse_toolkit.aws.mysql.replica_set.ASGInstance")
    @patch("infrahouse_toolkit.aws.mysql.replica_set.EC2Instance")
    @patch.object(MySQLReplicaSet, "get_master_instance_id", return_value="i-existing-master")
    @patch.object(MySQLReplicaSet, "_bootstrap_as_replica")
    def test_becomes_replica(
        self,
        mock_replica: MagicMock,
        mock_get_master: MagicMock,
        mock_ec2_cls: MagicMock,
        mock_asg_inst_cls: MagicMock,
        tmp_path,
    ) -> None:
        """Subsequent instance becomes replica when master exists."""
        mock_ec2 = mock_ec2_cls.return_value
        mock_ec2.instance_id = "i-new"
        marker = str(tmp_path / "marker")

        rs = MySQLReplicaSet(
            cluster_id="c",
            dynamodb_table="t",
            credentials_secret="s",
            vpc_cidr="10.0.0.0/16",
            aws_region="us-east-1",
            bootstrap_marker=marker,
        )
        rs._table_instance = MagicMock()
        rs._table_instance.lock.return_value.__enter__ = MagicMock()
        rs._table_instance.lock.return_value.__exit__ = MagicMock(return_value=False)

        rs.bootstrap()

        mock_replica.assert_called_once()
        args = mock_replica.call_args[0]
        assert args[1] == "i-existing-master"
        # Verify the EC2 instance was tagged with mysql_role=replica
        mock_ec2.add_tag.assert_called_once_with(key="mysql_role", value="replica")
        # Verify scale-in protection was NOT enabled for replica
        mock_asg_inst_cls.assert_not_called()
        # Marker is written as the very last step
        assert os.path.exists(marker)
        with open(marker, encoding="utf-8") as fh:
            assert fh.read() == "replica\n"


class TestInstanceDiscovery:
    """Tests for instances, master, and replicas properties."""

    @patch("infrahouse_toolkit.aws.mysql.replica_set.ASG")
    @patch("infrahouse_toolkit.aws.mysql.replica_set.EC2Instance")
    def test_instances(self, mock_ec2_cls: MagicMock, mock_asg_cls: MagicMock, replica_set: MySQLReplicaSet) -> None:
        """Returns MySQLInstance for each ASG instance."""
        asg_inst1 = MagicMock()
        asg_inst1.instance_id = "i-aaa"
        asg_inst2 = MagicMock()
        asg_inst2.instance_id = "i-bbb"
        mock_asg_cls.return_value.instances = [asg_inst1, asg_inst2]

        result = replica_set.instances
        assert len(result) == 2
        assert all(isinstance(i, MySQLInstance) for i in result)
        mock_asg_cls.assert_called_once_with("test-cluster")

    @patch("infrahouse_toolkit.aws.mysql.replica_set.ASG")
    @patch("infrahouse_toolkit.aws.mysql.replica_set.EC2Instance")
    def test_master_found(self, mock_ec2_cls: MagicMock, mock_asg_cls: MagicMock, replica_set: MySQLReplicaSet) -> None:
        """Returns the instance tagged as master."""
        asg_master = MagicMock()
        asg_master.instance_id = "i-master"
        asg_replica = MagicMock()
        asg_replica.instance_id = "i-replica"
        mock_asg_cls.return_value.instances = [asg_master, asg_replica]

        ec2_master = MagicMock()
        ec2_master.tags = {"mysql_role": "master"}
        ec2_replica = MagicMock()
        ec2_replica.tags = {"mysql_role": "replica"}
        mock_ec2_cls.side_effect = [ec2_master, ec2_replica]

        master = replica_set.master
        assert master is not None
        assert master.instance_id == ec2_master.instance_id

    @patch("infrahouse_toolkit.aws.mysql.replica_set.ASG")
    @patch("infrahouse_toolkit.aws.mysql.replica_set.EC2Instance")
    def test_master_not_found(
        self, mock_ec2_cls: MagicMock, mock_asg_cls: MagicMock, replica_set: MySQLReplicaSet
    ) -> None:
        """Returns None when no instance is tagged as master."""
        asg_inst = MagicMock()
        asg_inst.instance_id = "i-aaa"
        mock_asg_cls.return_value.instances = [asg_inst]

        ec2_inst = MagicMock()
        ec2_inst.tags = {"mysql_role": "replica"}
        mock_ec2_cls.return_value = ec2_inst

        assert replica_set.master is None

    @patch("infrahouse_toolkit.aws.mysql.replica_set.ASG")
    @patch("infrahouse_toolkit.aws.mysql.replica_set.EC2Instance")
    def test_replicas(self, mock_ec2_cls: MagicMock, mock_asg_cls: MagicMock, replica_set: MySQLReplicaSet) -> None:
        """Returns only instances tagged as replica."""
        asg_master = MagicMock()
        asg_master.instance_id = "i-master"
        asg_r1 = MagicMock()
        asg_r1.instance_id = "i-r1"
        asg_r2 = MagicMock()
        asg_r2.instance_id = "i-r2"
        mock_asg_cls.return_value.instances = [asg_master, asg_r1, asg_r2]

        ec2_master = MagicMock()
        ec2_master.tags = {"mysql_role": "master"}
        ec2_r1 = MagicMock()
        ec2_r1.tags = {"mysql_role": "replica"}
        ec2_r2 = MagicMock()
        ec2_r2.tags = {"mysql_role": "replica"}
        mock_ec2_cls.side_effect = [ec2_master, ec2_r1, ec2_r2]

        replicas = replica_set.replicas
        assert len(replicas) == 2


class TestBackupRestore:
    """Tests for backup/restore integration in bootstrap flow."""

    def test_master_takes_backup_when_s3_tag_present(self, replica_set: MySQLReplicaSet) -> None:
        """Master takes backup when percona:s3_bucket tag is set."""
        instance = MagicMock()
        instance.s3_bucket = "my-bucket"
        instance.instance_id = "i-master"

        replica_set._bootstrap_as_master(instance)

        instance.create_mysql_users.assert_called_once()
        instance.backup_to_s3.assert_called_once()

    def test_master_skips_backup_when_no_s3_tag(self, replica_set: MySQLReplicaSet) -> None:
        """Master skips backup when percona:s3_bucket tag is absent."""
        instance = MagicMock()
        instance.s3_bucket = None
        instance.instance_id = "i-master"

        replica_set._bootstrap_as_master(instance)

        instance.create_mysql_users.assert_called_once()
        instance.backup_to_s3.assert_not_called()

    @patch("infrahouse_toolkit.aws.mysql.replica_set.EC2Instance")
    def test_replica_restores_before_replication(self, mock_ec2_cls: MagicMock, replica_set: MySQLReplicaSet) -> None:
        """Replica restores from S3 before configuring replication."""
        mock_ec2_cls.return_value.private_ip = "10.0.1.1"

        instance = MagicMock()
        instance.s3_bucket = "my-bucket"

        replica_set._bootstrap_as_replica(instance, "i-master")

        instance.restore_from_s3.assert_called_once()
        instance.configure_replication.assert_called_once_with("10.0.1.1")
        instance.wait_for_replication_sync.assert_called_once()

    @patch("infrahouse_toolkit.aws.mysql.replica_set.EC2Instance")
    def test_replica_skips_restore_when_no_s3_tag(self, mock_ec2_cls: MagicMock, replica_set: MySQLReplicaSet) -> None:
        """Replica skips restore when percona:s3_bucket tag is absent."""
        mock_ec2_cls.return_value.private_ip = "10.0.1.1"

        instance = MagicMock()
        instance.s3_bucket = None

        replica_set._bootstrap_as_replica(instance, "i-master")

        instance.restore_from_s3.assert_not_called()
        instance.configure_replication.assert_called_once()
        instance.wait_for_replication_sync.assert_called_once()
