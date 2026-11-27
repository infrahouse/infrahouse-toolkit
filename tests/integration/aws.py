"""
The AWS side of the integration test: the jumphost's Auto Scaling group, its instance over SSM, and instance
refreshes.
"""

import json
import logging
from dataclasses import dataclass
from time import monotonic, sleep
from typing import Dict, Iterable, List

from boto3 import Session
from botocore.exceptions import ClientError
from infrahouse_core.aws.asg_instance import ASGInstance
from infrahouse_core.aws.exceptions import IHBootstrapException

from tests.integration.apt import AptPolicy

LOG = logging.getLogger(__name__)

BOOTSTRAP_MARKER = "/var/run/puppet-done"
"""ih-bootstrap touches it after its ``ih-puppet`` run succeeded (terraform-aws-cloud-init's ``ih-bootstrap.sh``)."""

EVIDENCE_COMMANDS = (
    "cloud-init status --long",
    "tail -n 100 /var/log/cloud-init-output.log",
)
"""What a failure collects from the instance, as infrahouse-core's ``wait_for_bootstrap()`` does."""

CONSOLE_TAIL_LINES = 60
"""Lines of the serial console a failure shows when SSM can't reach the instance."""

FACTER = "/opt/puppetlabs/bin/facter"

ACTIVE_REFRESH_STATUSES = ("Pending", "InProgress", "Cancelling", "RollbackInProgress", "Baking")
"""Instance refresh statuses that aren't final."""


class CommandFailed(AssertionError):
    """A command on the instance exited non-zero where the check needs it to succeed."""


class BootstrapFailed(AssertionError):
    """cloud-init or ih-bootstrap didn't finish on the instance."""


@dataclass(frozen=True)
class CommandResult:
    """
    A command that ran on the instance over SSM.

    :param instance_id: The instance.
    :param command: The shell command.
    :param exit_code: Its exit code.
    :param stdout: Its standard output, as SSM returns it (at most 24,000 characters).
    :param stderr: Its standard error, the same way.
    """

    instance_id: str
    command: str
    exit_code: int
    stdout: str
    stderr: str

    def __str__(self) -> str:
        return (
            f"{self.instance_id}$ {self.command}\n"
            f"exit code: {self.exit_code}\n"
            f"--- stdout ---\n{self.stdout}\n"
            f"--- stderr ---\n{self.stderr}"
        )


class CandidateNode:
    """
    An instance of the jumphost's group, reached over SSM.

    :param instance_id: EC2 instance id.
    :type instance_id: str
    :param session: boto3 session of the test role.
    :type session: Session
    :param region: AWS region.
    :type region: str
    """

    def __init__(self, instance_id: str, session: Session, region: str):
        self._instance = ASGInstance(instance_id=instance_id, session=session, region=region)

    # --- Public properties ---

    @property
    def apt_policy(self) -> AptPolicy:
        """
        :return: ``apt-cache policy infrahouse-toolkit`` on the instance.
        :raise CommandFailed: If the command fails.
        """
        return AptPolicy(self.run("apt-cache policy infrahouse-toolkit", check=True).stdout)

    @property
    def evidence(self) -> str:
        """
        ``cloud-init status --long`` and the tail of ``/var/log/cloud-init-output.log``.

        Best effort: it runs on a path that is already failing, often because SSM can't reach the instance, so a
        command that fails here doesn't replace the failure it explains, and short timeouts keep it quick.

        :return: The commands and their output, for a failure message.
        """
        report = [f"===== evidence from {self.instance_id} ====="]
        ssm_failed = False
        for command in EVIDENCE_COMMANDS:
            try:
                report.append(str(self.run(command, send_timeout=60, execution_timeout=60)))
            except (ClientError, RuntimeError, TimeoutError) as err:
                ssm_failed = True
                report.append(f"{self.instance_id}$ {command}\n<unavailable: {err}>")
        if ssm_failed:
            report.append(self._console_output)
        return "\n".join(report)

    @property
    def installed_version(self) -> str:
        """
        :return: The version of infrahouse-toolkit that dpkg has installed.
        :raise CommandFailed: If the package isn't installed.
        """
        return self.run("dpkg-query -W -f='${Version}' infrahouse-toolkit", check=True).stdout.strip()

    @property
    def instance_id(self) -> str:
        """
        :return: EC2 instance id.
        """
        return self._instance.instance_id

    @property
    def puppet_facts(self) -> Dict:
        """
        The facts ``profile::puppet_apply`` builds the cron's ``ih-puppet`` command from.

        :return: ``{"ih-puppet": {...}, "puppet_environment": "..."}``, as terraform-aws-cloud-init writes them.
        :raise CommandFailed: If facter fails.
        """
        return json.loads(self.run(f"{FACTER} -p --json ih-puppet puppet_environment", check=True).stdout)

    # --- Public methods ---

    def protect(self) -> None:
        """Protect the instance from scale-in, which also keeps an instance refresh from replacing it."""
        self._instance.protect()

    def run(
        self, command: str, check: bool = False, send_timeout: int = 600, execution_timeout: int = 60
    ) -> CommandResult:
        """
        Run a shell command on the instance over SSM, as root.

        :param command: The command, for ``AWS-RunShellScript``.
        :type command: str
        :param check: Raise if the command exits non-zero.
        :type check: bool
        :param send_timeout: Seconds to keep trying to send it, while the SSM agent isn't registered yet.
        :type send_timeout: int
        :param execution_timeout: Seconds to wait for it to finish.
        :type execution_timeout: int
        :return: The result.
        :raise CommandFailed: If ``check`` is set and the command exits non-zero.
        """
        exit_code, stdout, stderr = self._instance.execute_command(
            command, send_timeout=send_timeout, execution_timeout=execution_timeout
        )
        result = CommandResult(self.instance_id, command, exit_code, stdout, stderr)
        if check and exit_code != 0:
            raise CommandFailed(str(result))
        return result

    def unprotect(self) -> None:
        """Remove the instance's scale-in protection."""
        self._instance.unprotect()

    def wait_for_bootstrap(self, timeout: int = 1800, poll_interval: int = 20) -> None:
        """
        Wait until cloud-init finished and ih-bootstrap's ``ih-puppet`` run succeeded.

        infrahouse-core's ``wait_for_bootstrap()`` waits for cloud-init: it reports ``done`` only after ih-bootstrap
        ran, and ``error`` if it failed, because the bootstrap script runs under ``set -euo pipefail``. Then
        ih-bootstrap's marker must exist.

        :param timeout: Seconds to wait.
        :type timeout: int
        :param poll_interval: Seconds between two status checks.
        :type poll_interval: int
        :raise BootstrapFailed: If cloud-init ends in ``error``, is still running after ``timeout``, or finished
            without ih-bootstrap's marker. The message carries the evidence.
        """
        try:
            self._instance.wait_for_bootstrap(timeout_seconds=timeout, poll_interval=poll_interval)
        except IHBootstrapException as err:
            raise BootstrapFailed(str(err)) from err

        if self.run(f"test -f {BOOTSTRAP_MARKER}").exit_code != 0:
            raise BootstrapFailed(
                f"cloud-init on {self.instance_id} finished, but {BOOTSTRAP_MARKER} is missing: "
                f"ih-bootstrap didn't finish.\n{self.evidence}"
            )
        LOG.info("%s finished bootstrapping, and %s exists.", self.instance_id, BOOTSTRAP_MARKER)

    # --- Private properties ---

    @property
    def _console_output(self) -> str:
        """
        :return: The tail of the instance's serial console, where cloud-init logs too, for when SSM can't reach it.
        """
        try:
            output = self._instance.ec2_client.get_console_output(InstanceId=self.instance_id, Latest=True)
        except ClientError as err:
            return f"===== serial console of {self.instance_id} =====\n<unavailable: {err}>"
        tail = "\n".join(output.get("Output", "").splitlines()[-CONSOLE_TAIL_LINES:])
        return f"===== serial console of {self.instance_id}, last {CONSOLE_TAIL_LINES} lines =====\n{tail}"


class InstanceRefresh:
    """
    An instance refresh of an Auto Scaling group.

    :param client: boto3 autoscaling client.
    :param asg_name: Group name.
    :type asg_name: str
    :param refresh_id: The refresh's id.
    :type refresh_id: str
    """

    def __init__(self, client, asg_name: str, refresh_id: str):
        self._client = client
        self._asg_name = asg_name
        self._refresh_id = refresh_id

    def __str__(self) -> str:
        description = self._description
        return (
            f"instance refresh {self._refresh_id} of {self._asg_name}: {description['Status']}"
            f" ({description.get('StatusReason', 'no reason given')})"
        )

    # --- Public properties ---

    @property
    def is_active(self) -> bool:
        """
        :return: Whether the refresh hasn't reached a final status yet.
        """
        return self.status in ACTIVE_REFRESH_STATUSES

    @property
    def refresh_id(self) -> str:
        """
        :return: The refresh's id.
        """
        return self._refresh_id

    @property
    def status(self) -> str:
        """
        :return: ``Pending``, ``InProgress``, ``Successful``, ``Cancelling``, ``Cancelled``, ``Failed``, and so on.
        """
        return self._description["Status"]

    # --- Public methods ---

    def cancel(self) -> None:
        """Cancel the refresh, if it is still active."""
        if self.is_active:
            LOG.info("Cancelling %s.", self)
            self._client.cancel_instance_refresh(AutoScalingGroupName=self._asg_name)

    def wait_for(self, statuses: Iterable[str], timeout: int, poll_interval: int = 10) -> str:
        """
        Wait until the refresh reaches one of the statuses, or a final one.

        :param statuses: Statuses to wait for, for example ``["InProgress"]``.
        :type statuses: Iterable[str]
        :param timeout: Seconds to wait.
        :type timeout: int
        :param poll_interval: Seconds between two checks.
        :type poll_interval: int
        :return: The status it reached: one of ``statuses``, or a final status.
        :raise AssertionError: If it reached neither within ``timeout``.
        """
        wanted = set(statuses)
        deadline = monotonic() + timeout
        while True:
            status = self.status
            if status in wanted or status not in ACTIVE_REFRESH_STATUSES:
                return status
            if monotonic() >= deadline:
                raise AssertionError(f"After {timeout} seconds, {self}; expected {', '.join(sorted(wanted))}.")
            LOG.info("%s", self)
            sleep(poll_interval)

    # --- Private properties ---

    @property
    def _description(self) -> Dict:
        return self._client.describe_instance_refreshes(
            AutoScalingGroupName=self._asg_name, InstanceRefreshIds=[self._refresh_id]
        )["InstanceRefreshes"][0]


class CandidateGroup:
    """
    The jumphost's Auto Scaling group: one instance with the toolkit candidate.

    :param asg_name: Group name.
    :type asg_name: str
    :param session: boto3 session of the test role.
    :type session: Session
    :param region: AWS region.
    :type region: str
    """

    def __init__(self, asg_name: str, session: Session, region: str):
        self._asg_name = asg_name
        self._session = session
        self._region = region
        self._client = session.client("autoscaling", region_name=region)

    # --- Public properties ---

    @property
    def autoscaling_client(self):
        """
        :return: The boto3 autoscaling client the group uses.
        """
        return self._client

    @property
    def name(self) -> str:
        """
        :return: Group name.
        """
        return self._asg_name

    @property
    def scaling_activities(self) -> str:
        """
        :return: The group's five latest scaling activities, one per line, for a failure message.
        """
        activities = self._client.describe_scaling_activities(AutoScalingGroupName=self._asg_name, MaxRecords=5)
        lines = [f"===== latest scaling activities of {self._asg_name} ====="]
        for activity in activities["Activities"]:
            lines.append(
                f"{activity['StartTime']:%Y-%m-%dT%H:%M:%S} {activity['StatusCode']}: {activity['Description']}"
                f" ({activity.get('StatusMessage') or activity.get('Cause', '')})"
            )
        return "\n".join(lines)

    # --- Public methods ---

    def start_instance_refresh(self, preferences: Dict) -> InstanceRefresh:
        """
        Start an instance refresh with the group's own launch template.

        :param preferences: ``Preferences`` for ``StartInstanceRefresh``. ``SkipMatching`` is always off: the
            instances already run the launch template, and the refresh must still replace them.
        :type preferences: dict
        :return: The refresh.
        """
        response = self._client.start_instance_refresh(
            AutoScalingGroupName=self._asg_name,
            Strategy="Rolling",
            Preferences={**preferences, "SkipMatching": False},
        )
        refresh = InstanceRefresh(self._client, self._asg_name, response["InstanceRefreshId"])
        LOG.info("Started %s.", refresh)
        return refresh

    def wait_for_in_service_node(self, timeout: int = 900, poll_interval: int = 15) -> CandidateNode:
        """
        Wait until the group has exactly one instance and it is ``InService``.

        :param timeout: Seconds to wait.
        :type timeout: int
        :param poll_interval: Seconds between two checks.
        :type poll_interval: int
        :return: The instance.
        :raise AssertionError: If it doesn't happen within ``timeout``. The message has the group's instances, its
            scaling activities and the evidence from each instance.
        """
        deadline = monotonic() + timeout
        while True:
            instances = self._instances
            if len(instances) == 1 and instances[0]["LifecycleState"] == "InService":
                return self._node(instances[0]["InstanceId"])
            if monotonic() >= deadline:
                states = ", ".join(f"{i['InstanceId']} {i['LifecycleState']}" for i in instances) or "no instances"
                evidence = "\n".join(self._node(i["InstanceId"]).evidence for i in instances)
                raise AssertionError(
                    f"{self._asg_name} has no single InService instance after {timeout} seconds: {states}.\n"
                    f"{self.scaling_activities}\n{evidence}"
                )
            LOG.info(
                "Waiting for one InService instance in %s. Now: %s",
                self._asg_name,
                ", ".join(f"{i['InstanceId']} {i['LifecycleState']}" for i in instances) or "no instances",
            )
            sleep(poll_interval)

    # --- Private properties ---

    @property
    def _instances(self) -> List[Dict]:
        return self._client.describe_auto_scaling_groups(AutoScalingGroupNames=[self._asg_name])["AutoScalingGroups"][
            0
        ]["Instances"]

    # --- Private methods ---

    def _node(self, instance_id: str) -> CandidateNode:
        return CandidateNode(instance_id, session=self._session, region=self._region)
