"""
Module for helper functions to deal with Terraform.
"""

import json
from base64 import b64decode

from infrahouse_toolkit.terraform.backends import get_backend
from infrahouse_toolkit.terraform.exceptions import IHParseError
from infrahouse_toolkit.terraform.status import RunOutput, RunResult, TFStatus, decolor


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
                metadata = json.loads(b64decode(comment_as_lines[idx].strip("`")))
                backend_url = list(metadata)[0]
                return TFStatus(
                    get_backend(backend_url),
                    success=metadata[backend_url]["success"],
                    run_result=RunResult(
                        metadata[backend_url]["add"],
                        metadata[backend_url]["change"],
                        metadata[backend_url]["destroy"],
                    ),
                    run_output=RunOutput(
                        metadata[backend_url]["stdout"],
                        metadata[backend_url]["stderr"],
                    ),
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
