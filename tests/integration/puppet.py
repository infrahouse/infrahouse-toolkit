"""
The Puppet side of the integration test: the Puppet cron's command and environment, and an ``ih-puppet`` run that
fails.
"""

import shlex
from textwrap import dedent
from typing import List

from tests.integration.aws import CandidateNode, CommandResult

PUPPET_WRAPPER = "/usr/local/bin/puppet-wrapper"
"""The Puppet cron's command (``profile::puppet_apply`` in puppet-code)."""

CRON_ENV = "env -i HOME=/root LOGNAME=root SHELL=/bin/sh PATH=/bin:/usr/bin:/usr/sbin:/usr/local/bin"
"""The environment the Puppet cron runs its command in: cron's own, with the ``PATH`` of ``profile::puppet_apply``."""

IH_PUPPET = "/usr/local/bin/ih-puppet"


class FailingPuppetRun:
    """
    ``ih-puppet --cancel-instance-refresh-on-error`` applying a manifest whose only resource fails, on the instance,
    in the cron's environment and with the arguments the Puppet cron's command has.

    ``profile::puppet_apply`` builds the cron's ``ih-puppet`` command from the ``ih-puppet`` and ``puppet_environment``
    facts; this builds it the same way, without ``--quiet``, so the output shows the cancel. The manifest is written on
    the instance: nothing in puppet-code changes.

    :param node: The instance.
    :type node: CandidateNode
    """

    MANIFEST = "/root/ih-192-failing.pp"
    LOG = "/root/ih-192-failing.log"

    def __init__(self, node: CandidateNode):
        self._node = node

    # --- Public properties ---

    @property
    def command(self) -> str:
        """
        :return: The shell command: it writes the manifest, applies it, prints the tail of ``ih-puppet``'s output and
            exits with its exit code.
        """
        return dedent(f"""
            cat > {self.MANIFEST} <<'EOF'
            exec {{ 'ih-192-deliberate-failure': command => '/bin/false' }}
            EOF
            {CRON_ENV} {shlex.join(self._ih_puppet_arguments)} > {self.LOG} 2>&1
            rc=$?
            tail -n 150 {self.LOG}
            exit $rc
            """).strip()

    # --- Public methods ---

    def run(self, timeout: int = 900) -> CommandResult:
        """
        Run it on the instance.

        :param timeout: Seconds to wait for ``ih-puppet`` to finish.
        :type timeout: int
        :return: The result. Its exit code is ``ih-puppet``'s.
        """
        return self._node.run(self.command, execution_timeout=timeout)

    # --- Private properties ---

    @property
    def _ih_puppet_arguments(self) -> List[str]:
        facts = self._node.puppet_facts
        ih_puppet = facts["ih-puppet"]
        return [
            IH_PUPPET,
            "--environment",
            facts["puppet_environment"],
            "--environmentpath",
            ih_puppet["environmentpath"],
            "--root-directory",
            ih_puppet["root-directory"],
            "--hiera-config",
            ih_puppet["hiera-config"],
            "--module-path",
            ih_puppet["module-path"],
            "--cancel-instance-refresh-on-error",
            "apply",
            self.MANIFEST,
        ]
