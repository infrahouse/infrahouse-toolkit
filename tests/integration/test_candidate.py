"""
IH-192: a fresh instance boots and runs Puppet with the infrahouse-toolkit candidate, in real AWS.

The checks run in this order on the same jumphost, and each one assumes the ones before it passed, so
``make test-integration`` runs pytest with ``-x``. A failure names its check first, then carries the evidence: the
group's scaling activities, and cloud-init's status and log from each of its instances.
"""

from pytest_infrahouse.utils import wait_for_instance_refresh

from tests.integration.apt import TESTING_REPO_CODENAME, TESTING_REPO_URL
from tests.integration.aws import CandidateGroup, Check
from tests.integration.puppet import CRON_ENV, PUPPET_WRAPPER, FailingPuppetRun

# apt-cache policy shows the testing repository as "https://testing-noble.infrahouse.com noble-testing/main ...".
TESTING_REPO_ORIGIN = f"{TESTING_REPO_URL.rstrip('/')} {TESTING_REPO_CODENAME}/main "


def test_1_boot(candidate_group: CandidateGroup) -> None:
    """
    Boot: the instance reaches InService, and cloud-init and ih-bootstrap, which runs the candidate's ``ih-puppet``,
    finished.

    terraform-aws-jumphost 6.1.1 has no launching lifecycle hook, so InService alone doesn't wait for the bootstrap:
    the check waits for cloud-init and ih-bootstrap's marker too.
    """
    with Check(1, "boot", candidate_group):
        node = candidate_group.wait_for_in_service_node()
        node.wait_for_bootstrap()


def test_2_package(candidate_group: CandidateGroup, toolkit_version: str) -> None:
    """
    The package: dpkg has the version under test, and apt has it from the testing repository.
    """
    with Check(2, "the package", candidate_group):
        node = candidate_group.wait_for_in_service_node()
        installed = node.installed_version
        policy = node.apt_policy
        assert installed == toolkit_version, (
            f"{node.instance_id} has infrahouse-toolkit {installed}, not {toolkit_version}, the version under test."
            f"\n{policy}"
        )
        origins = policy.origins(toolkit_version)
        assert any(origin.startswith(TESTING_REPO_ORIGIN) for origin in origins), (
            f"apt-cache policy on {node.instance_id} doesn't show {toolkit_version} from "
            f"{TESTING_REPO_ORIGIN.strip()}. It shows it from: {origins}.\n{policy}"
        )


def test_3_puppet(candidate_group: CandidateGroup) -> None:
    """
    Puppet: the Puppet cron's command exits 0, in the cron's environment.
    """
    with Check(3, "Puppet", candidate_group):
        node = candidate_group.wait_for_in_service_node()
        result = node.run(f"{CRON_ENV} {PUPPET_WRAPPER}", execution_timeout=1200)
        if result.exit_code != 0:
            summary = node.run("cat /opt/puppetlabs/puppet/public/last_run_summary.yaml")
            raise AssertionError(
                f"{PUPPET_WRAPPER} on {node.instance_id} exited {result.exit_code}.\n{result}\n{summary}"
            )


def test_4_puppet_failure_cancels_refresh(candidate_group: CandidateGroup) -> None:
    """
    Puppet's failure path: with an instance refresh in progress, ``ih-puppet --cancel-instance-refresh-on-error``
    with a manifest that fails exits non-zero, and the refresh ends Cancelled.

    The instance is protected from scale-in, so the refresh waits for it (``ScaleInProtectedInstances: Wait``) and
    stays in progress, without replacing the instance that is running ``ih-puppet``.
    """
    with Check(4, "Puppet's failure path", candidate_group):
        node = candidate_group.wait_for_in_service_node()
        node.protect()
        refresh = None
        try:
            refresh = candidate_group.start_instance_refresh(
                {"MinHealthyPercentage": 100, "ScaleInProtectedInstances": "Wait"}
            )
            status = refresh.wait_for(["InProgress"], timeout=300)
            assert (
                status == "InProgress"
            ), f"The refresh never got in progress, so there is nothing to cancel: {refresh}."

            result = FailingPuppetRun(node).run()
            assert result.exit_code != 0, f"ih-puppet exited 0 with a manifest that fails.\n{result}"

            # ih-puppet's cancel request returns before ih-puppet exits: a refresh still in progress wasn't cancelled.
            status = refresh.status
            if status == "Cancelling":
                status = refresh.wait_for(["Cancelled"], timeout=600)
            assert (
                status == "Cancelled"
            ), f"ih-puppet exited {result.exit_code}, but {refresh}, not Cancelled.\n{result}"
        finally:
            # Leave the group as check 5 needs it: no refresh in progress, and nothing protected.
            if refresh is not None:
                refresh.cancel()
                refresh.wait_for(["Cancelled"], timeout=600)
            node.unprotect()


def test_5_replacement(candidate_group: CandidateGroup, toolkit_version: str) -> None:
    """
    Replacement: an instance refresh replaces the instance, and the new one boots, installs the same version and
    reaches InService.
    """
    with Check(5, "replacement", candidate_group):
        old_node = candidate_group.wait_for_in_service_node()
        # terraform-aws-jumphost's own refresh preference.
        refresh = candidate_group.start_instance_refresh({"MinHealthyPercentage": 100})
        wait_for_instance_refresh(
            asg_name=candidate_group.name,
            autoscaling_client=candidate_group.autoscaling_client,
            timeout=3600,
            poll_interval=30,
        )
        assert refresh.status == "Successful", f"{refresh}."

        new_node = candidate_group.wait_for_in_service_node()
        assert (
            new_node.instance_id != old_node.instance_id
        ), f"{refresh} succeeded, but {old_node.instance_id} is still the group's instance."
        new_node.wait_for_bootstrap()
        installed = new_node.installed_version
        assert installed == toolkit_version, (
            f"The new instance {new_node.instance_id} has infrahouse-toolkit {installed}, not {toolkit_version}.\n"
            f"{new_node.apt_policy}"
        )
