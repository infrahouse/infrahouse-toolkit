"""
.. topic:: ``ih-puppet apply``

    A ``ih-puppet apply`` subcommand.

    See ``ih-puppet apply`` for more details.
"""

from os import environ
from subprocess import run

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
        run(cmd, check=True, env=env)
