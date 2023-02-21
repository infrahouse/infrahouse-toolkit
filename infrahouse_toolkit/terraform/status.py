"""
Module for :py:class:`TFStatus`, Terraform plan run status class.
"""

import json
import re
from base64 import b64encode
from collections import namedtuple

from tabulate import tabulate

from infrahouse_toolkit import DEFAULT_OPEN_ENCODING
from infrahouse_toolkit.terraform.backends.tfbackend import TFBackend

RunResult = namedtuple("RunResult", "add change destroy")
RunOutput = namedtuple("RunOutput", "stdout stderr")


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
            + f"""<details>\n<summary>STDOUT</summary>\n\n```{decolor(self.stdout) or "no output"}```\n</details>\n"""
            + f"""<details>\n<summary>STDERR</summary>\n\n```{decolor(self.stderr) or "no output"}```\n</details>\n"""
            + f"""<details><summary><i>metadata</i></summary>\n<p>\n```{self.metadata}```\n</p></details>"""
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
                self.add if self.success else "❔",
                self.change if self.success else "❔",
                self.destroy if self.success else "❔",
            ]
        ]
        return tabulate(
            rows,
            headers=[
                "Success",
                f"{'🟢' if self.success and self.add > 0 else ''} Add",
                f"{'🟡' if self.success and self.change > 0 else ''} Change",
                f"{'🔴' if self.success and self.destroy > 0 else ''} Destroy",
            ],
            colalign=("center",),
            tablefmt="pipe",
        )

    @property
    def summary_resources(self):
        """
        Produces a string with a table that lists all added/modified/deleted resources.
        """
        if self.affected_resources:
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

        return None

    def __eq__(self, other):
        return all(getattr(self, x) == getattr(other, x) for x in self.__dict__ if x != "affected_resources")

    def __repr__(self):
        return json.dumps(
            {
                self.backend.id: {
                    "success": self.success,
                    "stdout": self.stdout,
                    "stderr": self.stderr,
                    "add": self.add,
                    "change": self.change,
                    "destroy": self.destroy,
                }
            }
        )
