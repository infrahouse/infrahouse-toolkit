"""
Module for helper functions to deal with Terraform.
"""

import json
import os
import time
from base64 import b64decode
from contextlib import contextmanager
from logging import getLogger
from subprocess import PIPE, CalledProcessError, Popen

from infrahouse_toolkit import DEFAULT_OPEN_ENCODING
from infrahouse_toolkit.terraform.backends import get_backend
from infrahouse_toolkit.terraform.exceptions import IHParseError
from infrahouse_toolkit.terraform.status import RunOutput, RunResult, TFStatus, decolor

DEFAULT_PROGRESS_INTERVAL = 10
LOG = getLogger()


def parse_comment(comment_text: str) -> TFStatus:
    """
    Given a text comment try to instantiate a Terraform status out of it.
    Not any comment can yield a status, obviously.
    A comment with the status will have a metadata in its content::

        <details><summary><i>metadata</i></summary>

    If parser failed because the comment doesn't have the status
    then the function will raise an exception.

    :param comment_text: Comment text.
    :return: Terraform status.
    :rtype: TFStatus
    :raise IHParseError: When the comment text doesn't contain a status.
    """
    try:
        comment_as_lines = [line.strip() for line in comment_text.split("\n")]
        metadata_index = comment_as_lines.index("<details><summary><i>metadata</i></summary>")
        for idx in range(metadata_index, len(comment_as_lines)):
            if comment_as_lines[idx].startswith("```"):
                metadata = json.loads(b64decode(comment_as_lines[idx + 1].strip("`")))
                backend_url = list(metadata)[0]
                return TFStatus(
                    get_backend(backend_url),
                    success=metadata[backend_url]["success"],
                    run_result=RunResult(
                        metadata[backend_url]["add"],
                        metadata[backend_url]["change"],
                        metadata[backend_url]["destroy"],
                    ),
                    run_output=RunOutput(None, None),
                )
    except (ValueError, AttributeError) as err:
        raise IHParseError(f"Failed to parse comment: {comment_text}") from err

    raise IHParseError(f"Failed to parse comment: {comment_text}")


def parse_plan(output) -> (RunResult, RunResult):
    """
    Parse a string given by output and return a tuple with execution plan.

    Credit for a regexp removing colors from text:
    https://stackoverflow.com/questions/14693701/how-can-i-remove-the-ansi-escape-sequences-from-a-string-in-python

    :param output: Output of terraform plan command.
    :type output: str
    :return: Two tuples. One tuple with number of changes (add, change, destroy).
        Another - with list of to be added/changed/destroyed resources.
    :rtype: RunResult, RunResult
    """
    counts = RunResult(None, None, None)
    resources = RunResult(None, None, None)

    if output is None:
        return counts, resources

    output = decolor(output)

    if any(
        pattern in output
        for pattern in [
            "No changes. Infrastructure is up-to-date.",
            "No changes. Your infrastructure matches the configuration.",
        ]
    ):
        return RunResult(0, 0, 0), RunResult([], [], [])

    if "Terraform will perform the following actions" not in output:
        return counts, resources

    try:
        resources = RunResult([], [], [])
        for line in output.splitlines():
            if line.startswith("::debug::"):
                continue

            if line.startswith("Plan: "):
                split_line = line.split()
                # Plan: 4 to add, 11 to change, 7 to destroy.
                counts = RunResult(int(split_line[1]), int(split_line[4]), int(split_line[7]))
            elif "will be created" in line:
                resources.add.append(line.split()[1])
            elif "will be destroyed" in line:
                resources.destroy.append(line.split()[1])
            elif "will be updated in-place" in line:
                resources.change.append(line.split()[1])

    except AttributeError:
        pass

    return counts, resources


@contextmanager
def terraform_apply(
    path,
    destroy_after=True,
    json_output=False,
    var_file="terraform.tfvars",
    enable_trace=False,
):
    """
    Run terraform init and apply, then return a generator.
    If destroy_after is True, run terraform destroy afterward.

    :param path: Path to directory with terraform module.
    :type path: str
    :param destroy_after: Run terraform destroy after context it returned back.
    :type destroy_after: bool
    :param json_output: Yield terraform output result as a dict (available in the context)
    :type json_output: bool
    :param var_file: Path to a file with terraform variables.
    :type var_file: str
    :param enable_trace: If True, it will run ``terraform`` with ``TF_LOG=JSON`` and
        save the terraform trace in ``tf-apply-trace.txt`` and ``tf-destroy-trace.txt``.
        Useful if you want to find out what API calls terraform makes and for other
        debugging.
    :type enable_trace: bool
    :return: If json_output is true then yield the result from terraform_output otherwise nothing.
        Use it in the ``with`` block.
    :raise CalledProcessError: if either of terraform commands (except ``terraform destroy``)
        exits with non-zero.
    """
    cmds = [
        ["terraform", "init", "-no-color"],
        ["terraform", "get", "-update=true", "-no-color"],
        [
            "terraform",
            "apply",
            f"-var-file={var_file}",
            "-input=false",
            "-auto-approve",
        ],
    ]
    env = dict(os.environ)
    if enable_trace:
        env["TF_LOG"] = "JSON"
    try:
        for cmd in cmds:
            stderr = open("tf-apply-trace.txt", "w", encoding=DEFAULT_OPEN_ENCODING) if enable_trace else None
            ret, cout, cerr = execute(cmd, stdout=None, stderr=stderr, cwd=path, env=env)
            if ret:
                raise CalledProcessError(returncode=ret, cmd=" ".join(cmd), output=cout, stderr=cerr)
        if json_output:
            yield terraform_output(path)
        else:
            yield

    finally:
        if destroy_after:
            stderr = open("tf-destroy-trace.txt", "w", encoding=DEFAULT_OPEN_ENCODING) if enable_trace else None
            execute(
                [
                    "terraform",
                    "destroy",
                    f"-var-file={var_file}",
                    "-input=false",
                    "-auto-approve",
                ],
                stdout=None,
                stderr=stderr,
                cwd=path,
                env=env,
            )


def terraform_output(path):
    """
    Run terraform output and return the json results as a dict.

    :param path: Path to directory with terraform module.
    :type path: str
    :return: dict from terraform output
    :rtype: dict
    """
    cmd = ["terraform", "output", "-json"]
    ret, cout, cerr = execute(cmd, stdout=PIPE, stderr=None, cwd=path)
    if ret:
        raise CalledProcessError(returncode=ret, cmd=" ".join(cmd), output=cout, stderr=cerr)
    return json.loads(cout)


def execute(
    cmd,
    stdout=PIPE,
    stderr=PIPE,
    cwd=None,
    env=None,
):
    """
    Execute a command and return a tuple with return code, STDOUT and STDERR.

    :param cmd: Command.
    :type cmd: list
    :param stdout: Where to send stdout. Default PIPE.
    :type stdout: int, None
    :param stderr: Where to send stdout. Default PIPE.
    :type stderr: int, None
    :param cwd: Working directory.
    :type cwd: str
    :param env: Dictionary with environment for the process.
    :type env: dict
    :return: Tuple (return code, STDOUT, STDERR)
    :rtype: tuple
    """
    LOG.info("Executing: %s", " ".join(cmd))
    with Popen(cmd, stdout=stdout, stderr=stderr, cwd=cwd, env=env) as proc:
        last_checking = time.time()
        while True:
            if proc.poll() is not None:
                break
            if time.time() - last_checking > DEFAULT_PROGRESS_INTERVAL:
                LOG.info("Still waiting for process to complete.")
                last_checking = time.time()
            time.sleep(1)

        cout, cerr = proc.communicate()
        return proc.returncode, cout, cerr
