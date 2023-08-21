"""
.. topic:: ``ih-puppet apply``

    A ``ih-puppet apply`` subcommand.

    See ``ih-puppet apply`` for more details.
"""
import sys
from os import environ
from subprocess import Popen

import click

from infrahouse_toolkit import LOG
from infrahouse_toolkit.lock.system import SystemLock


@click.command(name="apply")
@click.argument("manifest", required=False)
@click.pass_context
def cmd_apply(ctx, manifest):
    """
    Apply puppet manifest
    """
    manifest = manifest or f"{ctx.obj['root_directory']}/environments/{ctx.obj['environment']}/manifests/site.pp"
    LOG.info("Applying puppet manifest in %s", manifest)
    cmd = ["puppet", "apply"]
    if ctx.obj["debug"]:
        cmd.append("-d")

    cmd.extend(
        [
            "--environment",
            ctx.obj["environment"],
            "--hiera_config",
            ctx.obj["hiera_config"],
            "--hiera_config",
            ctx.obj["hiera_config"],
            f"--modulepath={ctx.obj['module_path']}",
            manifest,
            "--write-catalog-summary",
            "--detailed-exitcodes",
        ]
    )

    with SystemLock("/var/run/ih-puppet-apply.lock"):
        LOG.debug("Executing %s", " ".join(cmd))
        env = {"PATH": f"{environ['PATH']}:/opt/puppetlabs/bin"}
        # First run is to update the puppet code
        with Popen(cmd, env=env) as proc:
            proc.communicate()

        # Second run is to apply whatever the new puppet code brings
        with Popen(cmd, env=env) as proc:
            proc.communicate()
            ret = proc.returncode
            LOG.debug("Exit code: %d", ret)
            if ret == 0:
                LOG.info("The run succeeded with no changes or failures; the system was already in the desired state.")
                sys.exit(0)
            elif ret == 1:
                LOG.error("The run failed.")
                sys.exit(ret)
            elif ret == 2:
                LOG.info("The run succeeded, and some resources were changed.")
                sys.exit(0)
            elif ret == 4:
                LOG.warning("The run succeeded, and some resources failed.")
                sys.exit(ret)
            elif ret == 6:
                LOG.warning("The run succeeded, and included both changes and failures.")
                sys.exit(ret)
            else:
                LOG.error("Unknown run state.")
                sys.exit(ret)
