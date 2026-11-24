"""
Fail when pylint is told to stop reporting calls that don't match their function's signature.

pylint reports such a call as ``no-value-for-parameter``, ``too-many-function-args`` or
``unexpected-keyword-arg``. v2.57.0 shipped a broken ``ih-aws autoscaling scale-in`` (issue #206) because
one of them was suppressed instead of fixed. This check fails on any pylint pragma that disables one of
them, in any Python file tracked by git, tests included, and on pylint configuration that disables them.

Pragmas are found the way pylint finds them: in comment tokens, parsed by pylint's own pragma parser. So
``disable =`` with spaces, several messages in one pragma, ``disable-next`` and message ids (``E1121``)
all count, and so does disabling the category, the checker or everything that includes these messages.

Usage, from anywhere in the repository::

    python scripts/check_pylint_disables.py

Exit code is 1 if anything is found.
"""

import subprocess
import sys
import tokenize
from collections import Counter
from pathlib import Path
from typing import Dict, Iterator, List, NamedTuple, Optional, Tuple

from pylint.utils.pragma_parser import OPTION_PO, PragmaParserError, parse_pragma

# The messages this check protects, by message id.
SIGNATURE_MESSAGES = {
    "E1120": "no-value-for-parameter",
    "E1121": "too-many-function-args",
    "E1123": "unexpected-keyword-arg",
}

# Pragma messages that disable the protected messages along with others:
# everything, the "error" category and the checker that emits them.
UMBRELLA_MESSAGES = {"all", "e", "error", "typecheck"}

# Pragma actions that disable messages, and those that disable a whole file.
DISABLE_ACTIONS = {"disable", "disable-next", "disable-msg"}
FILE_ACTIONS = {"disable-all", "skip-file"}

# Suppressions that predate this check: (path, message) -> how many are allowed.
ALLOWLIST: Dict[Tuple[str, str], int] = {
    # elasticsearch 8.12's CatClient.snapshots() signature doesn't list request_timeout, though it works.
    ("infrahouse_toolkit/cli/ih_elastic/cmd_cat/cmd_snapshots/__init__.py", "unexpected-keyword-arg"): 1,
}


class Suppression(NamedTuple):
    """
    A pylint pragma that stops the protected messages from being reported.

    :param path: File path, relative to the repository root.
    :param line: Line number of the pragma.
    :param action: Pragma action, e.g. ``disable`` or ``skip-file``.
    :param message: The protected message's symbolic name, or the broader name that includes it.
    """

    path: str
    line: int
    action: str
    message: str

    def __str__(self) -> str:
        pragma = self.action if self.action in FILE_ACTIONS else f"{self.action}={self.message}"
        return f"{self.path}:{self.line}: pylint: {pragma}"


class SourceFile:
    """
    A Python source file, read for pylint pragmas.

    :param root: Repository root.
    :param path: File path, relative to ``root``.
    """

    def __init__(self, root: Path, path: str):
        self._root = root
        self._path = path

    @property
    def path(self) -> str:
        """
        :return: File path, relative to the repository root.
        """
        return self._path

    @property
    def suppressions(self) -> List[Suppression]:
        """
        :return: Every pragma in the file that stops the protected messages from being reported.
        """
        return list(self._find_suppressions())

    def _find_suppressions(self) -> Iterator[Suppression]:
        with open(self._root / self._path, "rb") as source:
            tokens = list(tokenize.tokenize(source.readline))
        for token in tokens:
            if token.type != tokenize.COMMENT:
                continue
            match = OPTION_PO.search(token.string)
            if match is None:
                continue
            line = token.start[0]
            for action, messages in self._parse(match.group(2)):
                if action in FILE_ACTIONS:
                    yield Suppression(self._path, line, action, action)
                elif action in DISABLE_ACTIONS:
                    for message in messages:
                        name = self._protected_name(message)
                        if name:
                            yield Suppression(self._path, line, action, name)

    @staticmethod
    def _parse(pragma: str) -> List[Tuple[str, List[str]]]:
        """
        Parse a pragma the way pylint does.

        :param pragma: The text after ``pylint:``.
        :return: (action, messages) pairs.
        """
        parsed = []
        try:
            for representer in parse_pragma(pragma):
                parsed.append((representer.action, representer.messages))
        except PragmaParserError:
            # pylint applies the part of a pragma before a syntax error and ignores the rest.
            pass
        return parsed

    @staticmethod
    def _protected_name(message: str) -> str:
        """
        :param message: A message as written in a pragma: an id, a symbolic name, a category or a checker.
        :return: The protected message's symbolic name, ``message`` itself if it includes the protected
            messages, or an empty string if it doesn't concern them.
        """
        folded = message.casefold()
        for msgid, name in SIGNATURE_MESSAGES.items():
            if folded in (msgid.casefold(), name):
                return name
        return folded if folded in UMBRELLA_MESSAGES else ""


class Repository:
    """
    The repository this script lives in.

    :param root: Repository root. Defaults to the parent of this script's directory.
    :param allowlist: Suppressions allowed per (path, message).
    """

    def __init__(
        self,
        root: Path = Path(__file__).resolve().parent.parent,
        allowlist: Optional[Dict[Tuple[str, str], int]] = None,
    ):
        self._root = root
        self._allowlist = ALLOWLIST if allowlist is None else allowlist

    @property
    def disabled_in_config(self) -> List[str]:
        """
        :return: Protected messages that pylint's configuration disables.
        """
        listing = subprocess.run(
            [sys.executable, "-m", "pylint", "--list-msgs-enabled"],
            cwd=self._root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        enabled = listing.split("Disabled messages:")[0]
        return [name for msgid, name in SIGNATURE_MESSAGES.items() if f"{name} ({msgid})" not in enabled]

    @property
    def python_files(self) -> List[str]:
        """
        :return: Python files tracked by git, relative to the repository root.
        """
        listing = subprocess.run(
            ["git", "ls-files", "-z", "--", "*.py"], cwd=self._root, capture_output=True, text=True, check=True
        ).stdout
        return [path for path in listing.split("\0") if path]

    @property
    def violations(self) -> List[Suppression]:
        """
        :return: Suppressions beyond what the allowlist allows. When a file has more suppressions of a
            message than allowed, all of them are listed, since there's no telling which one is new.
        """
        suppressions = [found for path in self.python_files for found in SourceFile(self._root, path).suppressions]
        counts = Counter((found.path, found.message) for found in suppressions)
        return [
            found
            for found in suppressions
            if counts[(found.path, found.message)] > self._allowlist.get((found.path, found.message), 0)
        ]


def main() -> None:
    """Report suppressed signature checks and exit 1 if there are any."""
    repository = Repository()
    violations = repository.violations
    disabled = repository.disabled_in_config
    for violation in violations:
        print(f"{violation}: this hides calls that don't match the function's signature; fix the call instead")
    for name in disabled:
        print(f"pylint configuration disables {name}; enable it")
    if violations or disabled:
        print(f"See {Path(__file__).name} for why these messages must stay enabled.")
        sys.exit(1)


if __name__ == "__main__":
    main()
