"""
.. topic:: ``ih-puppet apply``

    A ``ih-puppet apply`` subcommand.

    See ``ih-puppet apply`` for more details.
"""

import json
import os
import re
import shutil
import sys
from logging import getLogger
from os import environ
from os import path as osp
from subprocess import PIPE, Popen, SubprocessError, run
from typing import List

import click

from infrahouse_toolkit import DEFAULT_OPEN_ENCODING
from infrahouse_toolkit.lock.system import SystemLock

LOG = getLogger()

CANCEL_IR_TIMEOUT = 120
"""Seconds ``ih-aws autoscaling cancel-instance-refresh`` may run before ``ih-puppet`` kills it."""


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
            "--write_catalog_summary",
            "--detailed-exitcodes",
        ]
    )

    cancel_ir = ctx.obj["cancel_instance_refresh_on_error"]
    try:
        ret = _run_apply(cmd, ctx.obj["module_path"].split(":"), quiet)

    except Exception as err:  # pylint: disable=broad-exception-caught
        LOG.exception(err)
        if cancel_ir:
            _cancel_ir(debug=ctx.obj["debug"], quiet=quiet)
        sys.exit(1)

    # Outside the try block, so the handler above can't cancel a second time.
    if cancel_ir and ret != 0:
        _cancel_ir(debug=ctx.obj["debug"], quiet=quiet)
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
            LOG.info("%s isn't a puppet module", osp.join(module_path, module))


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


def _run_apply(cmd: List[str], module_path: List[str], quiet: bool) -> int:
    """
    Install Puppet module dependencies and run Puppet twice.

    :param cmd: The ``puppet apply`` command.
    :type cmd: list
    :param module_path: Directories with Puppet modules.
    :type module_path: list
    :param quiet: Discard Puppet's standard output.
    :type quiet: bool
    :return: The exit code for ``ih-puppet``: Puppet's detailed exit code, except that 2
        (changes, no failures) becomes 0.
    :rtype: int
    """
    with SystemLock("/var/run/ih-puppet-apply.lock"):
        env = {"PATH": f"{environ['PATH']}:/opt/puppetlabs/bin"}
        for path in module_path:
            if osp.exists(path):
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
            elif ret == 1:
                LOG.error("The run failed.")
            elif ret == 2:
                LOG.info("The run succeeded, and some resources were changed.")
                ret = 0
            elif ret == 4:
                LOG.warning("The run succeeded, and some resources failed.")
            elif ret == 6:
                LOG.warning("The run succeeded, and included both changes and failures.")
            else:
                LOG.error("Unknown run state.")
            return ret


def _cancel_ir(debug: bool = False, quiet: bool = False) -> None:
    """
    Cancel the instance refresh of the local instance's autoscaling group.

    The cancel runs ``ih-aws autoscaling cancel-instance-refresh`` in a child process.
    Puppet may have upgraded infrahouse-toolkit during this run, and then this process
    can't load modules or botocore data from the replaced install tree. A child process
    starts on whatever is installed by then. For the same reason, everything this function
    uses must be imported at module level.

    A failed cancel is logged and not raised, so it never changes the exit code of ``ih-puppet``.

    :param debug: Run ``ih-aws`` with ``--debug``.
    :type debug: bool
    :param quiet: Run ``ih-aws`` without ``--verbose``.
    :type quiet: bool
    """
    try:
        cmd = [_ih_aws_path()]
        if debug:
            cmd.append("--debug")
        if not quiet:
            cmd.append("--verbose")
        cmd.extend(["autoscaling", "cancel-instance-refresh"])
        LOG.info("Cancelling the instance refresh: %s", " ".join(cmd))
        run(cmd, check=True, timeout=CANCEL_IR_TIMEOUT)

    except (OSError, SubprocessError) as err:
        LOG.warning("Couldn't cancel the instance refresh: %s", err)


def _ih_aws_path() -> str:
    """
    Locate ``ih-aws`` next to the Python interpreter that runs ``ih-puppet``, or on ``PATH``.

    The package installs ``ih-aws`` in the same directory as its interpreter,
    while Puppet's cron ``PATH`` may not include ``/usr/local/bin``.

    :return: Path to the ``ih-aws`` executable.
    :raise FileNotFoundError: If ``ih-aws`` is in neither place.
    """
    candidate = osp.join(osp.dirname(sys.executable), "ih-aws")
    if osp.isfile(candidate) and os.access(candidate, os.X_OK):
        return candidate

    found = shutil.which("ih-aws")
    if found is None:
        raise FileNotFoundError(f"ih-aws is neither next to {sys.executable} nor on PATH")
    return found
