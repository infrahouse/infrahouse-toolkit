"""A fake executable for ``ih-puppet`` tests."""

from pathlib import Path
from typing import List


class FakeExecutable:
    """
    A shell script that stands in for ``ih-aws`` or ``puppet`` and records how it was run.

    :param path: Where to write the script.
    :type path: pathlib.Path
    """

    def __init__(self, path: Path):
        self._path = path
        self._log = path.with_name(f"{path.name}.calls")

    @property
    def calls(self) -> List[str]:
        """
        :return: One line per run: the path it was run as, then its arguments, separated by spaces.
        """
        return self._log.read_text().splitlines() if self._log.exists() else []

    @property
    def path(self) -> Path:
        """
        :return: Path to the script.
        """
        return self._path

    def write(self, body: str = "exit 0", interpreter: str = "/bin/sh") -> None:
        """
        Write the script.

        :param body: Shell commands that run after the call is recorded.
        :type body: str
        :param interpreter: Interpreter in the shebang line.
        :type interpreter: str
        """
        self._path.write_text(f'#!{interpreter}\necho "$0 $*" >> {self._log}\n{body}\n')
        self._path.chmod(0o755)
