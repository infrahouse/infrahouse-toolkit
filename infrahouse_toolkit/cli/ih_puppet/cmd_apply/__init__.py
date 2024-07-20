"""
.. topic:: ``ih-puppet apply``

    A ``ih-puppet apply`` subcommand.

    See ``ih-puppet apply`` for more details.
"""

import json
import os
import re
import sys
from logging import getLogger
from os import environ
from os import path as osp
from subprocess import PIPE, Popen

import click

from infrahouse_toolkit import DEFAULT_OPEN_ENCODING
from infrahouse_toolkit.lock.system import SystemLock

LOG = getLogger()


@click.command(name="apply")
@click.argument("manifest", required=False)
@click.pass_context
def cmd_apply(ctx, manifest):
    """
    Apply puppet manifest
    """
    manifest = manifest or f"{ctx.obj['root_directory']}/environments/{ctx.obj['environment']}/manifests/site.pp"
    LOG.info("Applying puppet manifest in %s", manifest)
    quiet = ctx.obj["quiet"]
    cmd = ["puppet", "apply"]
    if ctx.obj["debug"]:
        cmd.append("-d")

    cmd.extend(
        [
            "--environment",
            ctx.obj["environment"],
            "--environmentpath",
            ctx.obj["environmentpath"],
            "--hiera_config",
            ctx.obj["hiera_config"],
            f"--modulepath={ctx.obj['module_path']}",
            manifest,
            "--write-catalog-summary",
            "--detailed-exitcodes",
        ]
    )

    with SystemLock("/var/run/ih-puppet-apply.lock"):
        env = {"PATH": f"{environ['PATH']}:/opt/puppetlabs/bin"}
        for path in ctx.obj["module_path"].split(":"):
            install_module_dependencies(module_path=path, env=env)
        LOG.debug("Executing %s", " ".join(cmd))
        # First run is to update the puppet code
        with Popen(
            cmd, env=env, stdout=open("/dev/null", "w", encoding=DEFAULT_OPEN_ENCODING) if quiet else None
        ) as proc:
            proc.communicate()

        # Second run is to apply whatever the new puppet code brings
        with Popen(
            cmd, env=env, stdout=open("/dev/null", "w", encoding=DEFAULT_OPEN_ENCODING) if quiet else None
        ) as proc:
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


def install_module_dependencies(module_path: str, env: dict = None):
    """
    Assuming each subdirectory in ``module_path`` is a puppet module,
    read its ``metadata.json`` and install puppet module dependencies
    in the same directory.

    :param module_path: Path to a directory with puppet modules.
    :type module_path: str
    :param env: Environment variables for the puppet command.
    :type env: dict
    """
    for module in os.listdir(module_path):
        LOG.info("Installing %s dependencies", module)
        try:
            with open(osp.join(module_path, module, "metadata.json"), encoding=DEFAULT_OPEN_ENCODING) as f_desc:
                deps = json.loads(f_desc.read())["dependencies"]
                for dep in deps:
                    cmd = [
                        "puppet",
                        "module",
                        "--render-as",
                        "json",
                        "--modulepath",
                        module_path,
                        "install",
                        dep["name"],
                        "-v",
                        dep["version_requirement"],
                    ]
                    kwargs = {"stdout": PIPE, "stderr": PIPE}
                    if env:
                        kwargs["env"] = env

                    with Popen(cmd, **kwargs) as proc:
                        cout, cerr = proc.communicate()
                        LOG.info("STDOUT: \n%s", strip_colors(cout.decode()))
                        ret = proc.returncode
                        LOG.debug("Exit code: %d", ret)
                        if ret != 0:
                            LOG.error("Command '%s' exited with %d.", " ".join(cmd), ret)
                            LOG.error("STDERR:\n%s", strip_colors(cerr.decode()))
                            sys.exit(1)
        except NotADirectoryError:
            LOG.info("%s isn't a puppet module")


def strip_colors(text: str) -> str:
    """
    Credit:
    https://stackoverflow.com/questions/14693701/how-can-i-remove-the-ansi-escape-sequences-from-a-string-in-python

    :param text: ANSI colored text
    :return: The input text w/o colors.
    """
    ansi_escape = re.compile(
        r"""
    \x1B  # ESC
    (?:   # 7-bit C1 Fe (except CSI)
        [@-Z\\-_]
    |     # or [ for CSI, followed by a control sequence
        \[
        [0-?]*  # Parameter bytes
        [ -/]*  # Intermediate bytes
        [@-~]   # Final byte
    )
""",
        re.VERBOSE,
    )
    return ansi_escape.sub("", text)
