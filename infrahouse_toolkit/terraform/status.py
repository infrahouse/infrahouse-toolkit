"""
Module for :py:class:`TFStatus`, Terraform plan run status class.
"""

import json
import logging
import re
from base64 import b64decode, b64encode
from collections import namedtuple
from difflib import unified_diff

from tabulate import tabulate

from infrahouse_toolkit import DEFAULT_OPEN_ENCODING
from infrahouse_toolkit.terraform.backends.tfbackend import TFBackend

RunResult = namedtuple("RunResult", "add change destroy")
RunOutput = namedtuple("RunOutput", "stdout stderr")

LOG = logging.getLogger()

RE_NO_COLOR = r"""
    \x1B  # ESC
    (?:   # 7-bit C1 Fe (except CSI)
        [@-Z\\-_]
    |     # or [ for CSI, followed by a control sequence
        \[
        [0-?]*  # Parameter bytes
        [ -/]*  # Intermediate bytes
        [@-~]   # Final byte
    )
"""


def decolor(text: str) -> str:
    """Remove ANSI escape sequences that color console output."""
    if text:
        ansi_escape = re.compile(RE_NO_COLOR, re.VERBOSE)
        return ansi_escape.sub("", text)

    return text


def strip_lines(src: str, pattern: str) -> str:
    """
    Remove lines starting with a string ``pattern``.

    :param src: Input text
    :type src: str
    :param pattern: A string. When a line in the input text starts with this string - skip it.
    :type pattern: str
    :return: Stripped text.
    :rtype: str
    """
    return (
        "\n".join([x for x in src.splitlines() if not x.startswith(pattern)]) + ("\n" if src[-1] == "\n" else "")
        if src
        else src
    )


class TFStatus:
    """
    :py:class:`TFStatus` represents a result of a ``terraform plan`` run.
    It includes outputs (both stdout and stderr) and a summary of changes -
    how many resources are going to be created/changed/destroyed.

    Credit for emojis https://emojicombos.com/
    """

    # pylint: disable=too-many-instance-attributes,too-many-arguments
    # Probably counts could be calculated from
    # affected_resources, but it's optional.
    def __init__(
        self,
        backend: TFBackend,
        success: bool,
        run_result: RunResult,
        run_output: RunOutput,
        affected_resources: RunResult = None,
    ):
        self.backend = backend
        self.success = success
        self.add = run_result.add
        self.change = run_result.change
        self.destroy = run_result.destroy
        self.stdout = run_output.stdout
        self.stderr = run_output.stderr
        self.affected_resources = affected_resources

    @property
    def comment(self):
        """Serialize the status as a comment text eligible to be posted on GitHub."""
        return (
            f"\n# State **`{self.backend.id}`**\n"
            + f"## Affected resources counts\n\n{self.summary_counts}\n"
            + (f"## Affected resources by action\n\n{self.summary_resources}\n" if self.affected_resources else "")
            + f"""<details>\n<summary>STDOUT</summary>\n\n```\n{self._short_stdout or "no output"}\n```\n</details>\n"""
            + f"""<details><summary><i>metadata</i></summary>\n\n```\n{self.metadata}\n```\n</details>"""
        )

    @property
    def metadata(self):
        """
        Produces a base64 encoded string with a dictionary that can be used
        to create the same instance of the class.
        """
        return b64encode(str(self).encode(DEFAULT_OPEN_ENCODING)).decode(DEFAULT_OPEN_ENCODING)

    @property
    def summary_counts(self):
        """
        Credit for tabulate:
        https://stackoverflow.com/questions/9535954/printing-lists-as-tabular-data

        :return: Formatted table.
        """
        rows = [
            [
                "✅" if self.success else "❌",
                self.add if self.success and self.add is not None else "❔",
                self.change if self.success and self.change is not None else "❔",
                self.destroy if self.success and self.destroy is not None else "❔",
            ]
        ]
        return tabulate(
            rows,
            headers=[
                "Success",
                f"{'🟢' if self.success and self.add is not None and self.add > 0 else ''} Add",
                f"{'🟡' if self.success and self.change is not None and self.change > 0 else ''} Change",
                f"{'🔴' if self.success and self.destroy is not None and self.destroy > 0 else ''} Destroy",
            ],
            colalign=("right",),
            tablefmt="pipe",
        )

    @property
    def summary_resources(self):
        """
        Produces a string with a table that lists all added/modified/deleted resources.
        """
        if all(
            (
                self.affected_resources,
                self.affected_resources.add is not None,
                self.affected_resources.change is not None,
                self.affected_resources.destroy is not None,
            )
        ):
            rows = (
                [["🟢", f"`{field}`"] for field in self.affected_resources.add]
                + [["🟡", f"`{field}`"] for field in self.affected_resources.change]
                + [["🔴", f"`{field}`"] for field in self.affected_resources.destroy]
            )
            return (
                tabulate(
                    rows,
                    headers=["Action", "Resources"],
                    colalign=("center",),
                    tablefmt="pipe",
                )
                if rows
                else ""
            )

        return "No affected resources"

    @property
    def _short_stdout(self):
        if self.stdout is None:
            return None
        output = decolor(self.stdout).splitlines()
        result_lines = []
        trigger_lines = [
            "Terraform has compared your real infrastructure against your configuration",
            "Terraform used the selected providers to generate the following execution",
        ]

        def _match(candidate):
            for trigger in trigger_lines:
                if candidate.startswith(trigger):
                    return True
            return False

        idx = 0
        # Find beginning of output we want to preserve
        while idx < len(output):
            if _match(output[idx]):
                break
            idx += 1

        # Save the rest of output
        while idx < len(output):
            result_lines.append(output[idx])
            if "~ user_data" in output[idx]:
                try:
                    parts = output[idx].split()
                    before = b64decode(parts[3].strip('"')).decode()
                    after = (
                        "(known after apply)"
                        if parts[5].strip('"') == "(known"
                        else b64decode(parts[5].strip('"')).decode()
                    )
                    result_lines.append("userdata changes:")
                    for diff_line in unified_diff(
                        before.splitlines(), after.splitlines(), fromfile="before", tofile="after", lineterm=""
                    ):
                        result_lines.append(diff_line)
                    result_lines.append("EOF userdata changes.")
                except UnicodeDecodeError as err:
                    LOG.warning("Failed to decode userdata: %s", err)
            idx += 1

        if result_lines:
            return "\n".join(result_lines)
        return "\n".join(output)

    def __eq__(self, other):
        return all(
            getattr(self, x) == getattr(other, x)
            for x in self.__dict__
            if x not in ["affected_resources", "stdout", "stderr"]
        )

    def __repr__(self):
        return json.dumps(
            {
                self.backend.id: {
                    "success": self.success,
                    "add": self.add,
                    "change": self.change,
                    "destroy": self.destroy,
                }
            }
        )
