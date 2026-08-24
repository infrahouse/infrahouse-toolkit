"""
RDS for MySQL DB instance.

Provides :class:`RDSMySQLInstance`, which extends
:class:`infrahouse_core.aws.RDSInstance` with the MySQL-specific reads a slow
query log audit needs, plus two control-plane operations: waiting for a
parameter change to land, and pulling log files off the instance.
"""

import time
from datetime import datetime, timedelta, timezone
from logging import getLogger
from os import path as osp
from typing import List, Optional

import boto3
import requests
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.exceptions import ClientError
from infrahouse_core.aws import RDSInstance, get_client

from infrahouse_toolkit import DEFAULT_OPEN_ENCODING
from infrahouse_toolkit.aws.rds.exceptions import RDSError, RDSInstanceNotFound
from infrahouse_toolkit.aws.rds.parameter_group import RDSParameterGroup

LOG = getLogger(__name__)


class RDSMySQLInstance(RDSInstance):
    """
    An RDS for MySQL DB instance.

    Inherits ``exists``, ``delete()``, ``db_instance_id`` and the lazy boto3
    client from :class:`infrahouse_core.aws.RDSInstance`.

    :param db_instance_id: DB instance identifier.
    :type db_instance_id: str
    :param region: AWS region.
    :type region: str
    :param role_arn: IAM role ARN for cross-account access.
    :type role_arn: str
    :param session: Pre-configured boto3 session.
    :type session: Session
    """

    def __init__(self, db_instance_id: str, region: str = None, role_arn: str = None, session=None) -> None:
        super().__init__(db_instance_id, region=region, role_arn=role_arn, session=session)
        self._description: Optional[dict] = None
        self._parameter_group: Optional[RDSParameterGroup] = None
        self._cloudwatch_client = None

    # --- Public properties ---

    @property
    def allocated_storage_bytes(self) -> int:
        """
        :return: Provisioned storage in bytes.
        :rtype: int
        """
        return self.description["AllocatedStorage"] * 1024**3

    @property
    def cloudwatch_log_exports(self) -> List[str]:
        """
        Log types this instance publishes to CloudWatch Logs.

        Note that ``slowquery`` appearing here does not mean anything is being
        published — RDS ships the log *file*, so with ``log_output=TABLE`` the
        export is configured but silent.

        :return: Enabled CloudWatch Logs exports.
        :rtype: List[str]
        """
        return self.description.get("EnabledCloudwatchLogsExports", [])

    @property
    def description(self) -> dict:
        """
        :return: Raw ``describe_db_instances`` entry for this instance.
        :rtype: dict
        :raises RDSInstanceNotFound: If the instance does not exist.
        :raises ClientError: On any other RDS API failure.
        """
        if self._description is None:
            try:
                response = self._client.describe_db_instances(DBInstanceIdentifier=self._resource_id)
            except ClientError as err:
                if err.response["Error"]["Code"] == "DBInstanceNotFound":
                    raise RDSInstanceNotFound(f"DB instance {self._resource_id} not found") from err
                raise
            self._description = response["DBInstances"][0]
        return self._description

    @property
    def engine(self) -> str:
        """
        :return: Engine name, e.g. ``mysql``.
        :rtype: str
        """
        return self.description["Engine"]

    @property
    def engine_version(self) -> str:
        """
        :return: Engine version, e.g. ``8.0.45``.
        :rtype: str
        """
        return self.description["EngineVersion"]

    @property
    def free_storage_bytes(self) -> Optional[int]:
        """
        Most recent ``FreeStorageSpace`` reading from CloudWatch.

        This is the metric that decides whether a capture is safe to run:
        RDS keeps log files on the instance volume, so a long capture at
        ``long_query_time=0`` eats the same space as the data.

        :return: Free bytes, or ``None`` when CloudWatch has no recent
            datapoint (the metric lags by a minute or two).
        :rtype: Optional[int]
        """
        now = datetime.now(timezone.utc)
        response = self._cloudwatch.get_metric_statistics(
            Namespace="AWS/RDS",
            MetricName="FreeStorageSpace",
            Dimensions=[{"Name": "DBInstanceIdentifier", "Value": self._resource_id}],
            StartTime=now - timedelta(minutes=15),
            EndTime=now,
            Period=60,
            Statistics=["Minimum"],
        )
        datapoints = response["Datapoints"]
        if not datapoints:
            return None
        latest = max(datapoints, key=lambda point: point["Timestamp"])
        return int(latest["Minimum"])

    @property
    def parameter_apply_status(self) -> str:
        """
        :return: ``ParameterApplyStatus`` of the attached parameter group,
            e.g. ``in-sync``, ``applying``, ``pending-reboot``.
        :rtype: str
        """
        return self.description["DBParameterGroups"][0]["ParameterApplyStatus"]

    @property
    def parameter_group(self) -> RDSParameterGroup:
        """
        :return: The parameter group attached to this instance.
        :rtype: RDSParameterGroup
        """
        if self._parameter_group is None:
            name = self.description["DBParameterGroups"][0]["DBParameterGroupName"]
            self._parameter_group = RDSParameterGroup(
                name, region=self._region, role_arn=self._role_arn, session=self._session
            )
        return self._parameter_group

    @property
    def performance_insights_enabled(self) -> bool:
        """
        :return: Whether Performance Insights is enabled.
        :rtype: bool
        """
        return bool(self.description.get("PerformanceInsightsEnabled"))

    @property
    def slow_log_files(self) -> List[dict]:
        """
        Slow query log files currently on the instance.

        RDS rotates ``slowquery/mysql-slowquery.log`` hourly, so a capture
        longer than an hour spans several files.

        :return: Entries with ``name``, ``size`` and ``last_written``
            (epoch milliseconds), newest last.
        :rtype: List[dict]
        """
        files = []
        paginator = self._client.get_paginator("describe_db_log_files")
        for page in paginator.paginate(DBInstanceIdentifier=self._resource_id, FilenameContains="slowquery"):
            for entry in page.get("DescribeDBLogFiles", []):
                files.append(
                    {
                        "name": entry["LogFileName"],
                        "size": entry["Size"],
                        "last_written": entry["LastWritten"],
                    }
                )
        return sorted(files, key=lambda entry: entry["last_written"])

    @property
    def slow_log_size(self) -> int:
        """
        :return: Combined size in bytes of all slow query log files on the instance.
        :rtype: int
        """
        return sum(entry["size"] for entry in self.slow_log_files)

    @property
    def status(self) -> str:
        """
        :return: DB instance status, e.g. ``available``.
        :rtype: str
        """
        return self.description["DBInstanceStatus"]

    @property
    def tags(self) -> dict:
        """
        :return: A dictionary with the DB instance tags.
        :rtype: dict
        """
        return {tag["Key"]: tag["Value"] for tag in self.description.get("TagList", [])}

    # --- Public methods ---

    def download_log_file(self, log_file_name: str, destination_dir: str) -> str:
        """
        Download one RDS log file to a local directory.

        Prefers the ``downloadCompleteLogFile`` REST endpoint, which streams the
        whole file in a single signed request.  Falls back to the paginated
        ``DownloadDBLogFilePortion`` API, which is correct but returns roughly a
        megabyte per call and is throttled — painful for a capture of any size.

        :param log_file_name: Log file name as reported by :attr:`slow_log_files`.
        :type log_file_name: str
        :param destination_dir: Local directory to write into.
        :type destination_dir: str
        :return: Path of the downloaded file.
        :rtype: str
        :raises RDSError: If the file cannot be downloaded.
        """
        destination = osp.join(destination_dir, log_file_name.replace("/", "-"))
        try:
            self._download_complete(log_file_name, destination)
        except requests.RequestException as err:
            LOG.warning("Streaming download of %s failed (%s), falling back to the portion API", log_file_name, err)
            self._download_portions(log_file_name, destination)
        LOG.info("Downloaded %s to %s", log_file_name, destination)
        return destination

    @classmethod
    def list_instances(
        cls,
        engine_prefix: str = "mysql",
        region: str = None,
        role_arn: str = None,
        session=None,
    ) -> List["RDSMySQLInstance"]:
        """
        List DB instances, by default only the MySQL ones.

        Each returned instance carries the description it was built from, so
        reading its engine, status or tags costs no extra API call.

        :param engine_prefix: Only return instances whose engine starts with
            this.  Pass an empty string for every engine.
        :type engine_prefix: str
        :param region: AWS region.
        :type region: str
        :param role_arn: IAM role ARN for cross-account access.
        :type role_arn: str
        :param session: Pre-configured boto3 session.
        :type session: Session
        :return: Matching instances, ordered by identifier.
        :rtype: List[RDSMySQLInstance]
        """
        if session is not None:
            client = session.client("rds", region_name=region)
        else:
            client = get_client("rds", region=region, role_arn=role_arn)

        instances = []
        for page in client.get_paginator("describe_db_instances").paginate():
            for description in page["DBInstances"]:
                if not description["Engine"].startswith(engine_prefix):
                    continue
                instance = cls(
                    description["DBInstanceIdentifier"],
                    region=region,
                    role_arn=role_arn,
                    session=session,
                )
                instance.seed_description(description)
                instances.append(instance)
        return sorted(instances, key=lambda entry: entry.db_instance_id)

    def refresh(self) -> None:
        """Drop cached instance state so the next read hits the API."""
        self._description = None

    def seed_description(self, description: dict) -> None:
        """
        Populate the cached description from an already-fetched payload.

        Lets a bulk ``describe_db_instances`` serve many instances without each
        of them making the call again.

        :param description: A ``DBInstances`` entry.
        :type description: dict
        """
        self._description = description

    def wait_parameters_in_sync(self, timeout: int = 600, poll_interval: int = 10, settle: int = 15) -> None:
        """
        Wait until the attached parameter group reports ``in-sync``.

        A short *settle* delay comes first because RDS needs a moment to move
        the status to ``applying``: polling immediately can observe the
        pre-change ``in-sync`` and return before anything has happened.

        :param timeout: Maximum seconds to wait.
        :type timeout: int
        :param poll_interval: Seconds between polls.
        :type poll_interval: int
        :param settle: Seconds to wait before the first poll.
        :type settle: int
        :raises RDSError: If the status becomes ``failed-to-apply`` or the
            timeout is exceeded.
        """
        time.sleep(settle)
        deadline = time.monotonic() + timeout
        while True:
            self.refresh()
            status = self.parameter_apply_status
            if status == "in-sync":
                LOG.info("Parameter group %s is in-sync", self.parameter_group.name)
                return
            if status == "failed-to-apply":
                raise RDSError(f"Parameter group {self.parameter_group.name} failed to apply")
            LOG.info("Parameter group %s status is %s, waiting", self.parameter_group.name, status)
            if time.monotonic() >= deadline:
                raise RDSError(
                    f"Parameter group {self.parameter_group.name} did not reach in-sync "
                    f"within {timeout}s (last status {status})"
                )
            time.sleep(poll_interval)

    # --- Private properties ---

    @property
    def _cloudwatch(self):
        """
        Lazy-loaded CloudWatch client, built the same way as the inherited RDS one.

        :return: A boto3 CloudWatch client.
        """
        if self._cloudwatch_client is None:
            if self._session is not None:
                self._cloudwatch_client = self._session.client("cloudwatch", region_name=self._region)
            else:
                self._cloudwatch_client = get_client("cloudwatch", region=self._region, role_arn=self._role_arn)
        return self._cloudwatch_client

    # --- Private methods ---

    def _download_complete(self, log_file_name: str, destination: str) -> None:
        """
        Download a log file through the ``downloadCompleteLogFile`` REST endpoint.

        boto3 does not expose this endpoint, so the request is signed by hand
        with SigV4.

        :param log_file_name: Log file name.
        :type log_file_name: str
        :param destination: Local path to write to.
        :type destination: str
        :raises RDSError: If the session carries no credentials.
        :raises requests.RequestException: On any HTTP-level failure.
        """
        session = self._session or boto3.Session(region_name=self._region)
        credentials = session.get_credentials()
        if credentials is None:
            raise RDSError("No AWS credentials available to sign the log download request")

        region = self._client.meta.region_name
        url = f"https://rds.{region}.amazonaws.com/v13/downloadCompleteLogFile/{self._resource_id}/{log_file_name}"
        request = AWSRequest(method="GET", url=url)
        SigV4Auth(credentials.get_frozen_credentials(), "rds", region).add_auth(request)

        with requests.get(url, headers=dict(request.headers), stream=True, timeout=(10, 900)) as response:
            response.raise_for_status()
            with open(destination, "wb") as descriptor:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    descriptor.write(chunk)

    def _download_portions(self, log_file_name: str, destination: str) -> None:
        """
        Download a log file through the paginated ``DownloadDBLogFilePortion`` API.

        :param log_file_name: Log file name.
        :type log_file_name: str
        :param destination: Local path to write to.
        :type destination: str
        """
        marker = "0"
        with open(destination, "w", encoding=DEFAULT_OPEN_ENCODING) as descriptor:
            while True:
                response = self._client.download_db_log_file_portion(
                    DBInstanceIdentifier=self._resource_id,
                    LogFileName=log_file_name,
                    Marker=marker,
                )
                if response.get("LogFileData"):
                    descriptor.write(response["LogFileData"])
                if not response.get("AdditionalDataPending"):
                    return
                marker = response["Marker"]
