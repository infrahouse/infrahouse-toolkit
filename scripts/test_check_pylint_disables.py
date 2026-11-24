"""Unit tests for ``check_pylint_disables.py``."""

import subprocess
from pathlib import Path

import pytest
from check_pylint_disables import Repository, SourceFile, Suppression


@pytest.mark.parametrize(
    "comment, expected",
    [
        ("# pylint: disable=too-many-function-args", "too-many-function-args"),
        ("#pylint:disable=too-many-function-args", "too-many-function-args"),
        ("# pylint: disable = too-many-function-args", "too-many-function-args"),
        ("# pylint: disable=missing-docstring, too-many-function-args", "too-many-function-args"),
        ("# pylint: disable=missing-docstring,no-value-for-parameter", "no-value-for-parameter"),
        ("# pylint: disable-next=unexpected-keyword-arg", "unexpected-keyword-arg"),
        ("# pylint: disable-msg=unexpected-keyword-arg", "unexpected-keyword-arg"),
        ("# pylint: disable=E1121", "too-many-function-args"),
        ("# pylint: disable=e1120", "no-value-for-parameter"),
        ("# pylint: disable=Too-Many-Function-Args", "too-many-function-args"),
        ("# pylint: disable=all", "all"),
        ("# pylint: disable=E", "e"),
        ("# pylint: disable=typecheck", "typecheck"),
        ("# noqa: E501  # pylint: disable=too-many-function-args", "too-many-function-args"),
        ("# pylint: disable=too-many-function-args  # a reason", "too-many-function-args"),
        ("# pylint: disable=too-many-function-args; a reason", "too-many-function-args"),
    ],
)
def test_disable_spellings(tmp_path, comment, expected):
    """A disable is found however it is spelled, including disables of what includes the message."""
    _write(tmp_path, "mod.py", f"call(1, 2)  {comment}\n")

    assert SourceFile(tmp_path, "mod.py").suppressions == [Suppression("mod.py", 1, _comment_action(comment), expected)]


@pytest.mark.parametrize("comment", ["# pylint: skip-file", "# pylint: disable-all"])
def test_file_wide_disable(tmp_path, comment):
    """A pragma that turns off every check in a file is found."""
    _write(tmp_path, "mod.py", f"{comment}\ncall(1, 2)\n")

    suppressions = SourceFile(tmp_path, "mod.py").suppressions

    assert [(found.line, found.message) for found in suppressions] == [(1, comment.split()[-1])]


@pytest.mark.parametrize(
    "source",
    [
        "call(1, 2)  # pylint: disable=too-many-arguments\n",
        "call(1, 2)  # pylint: enable=too-many-function-args\n",
        "call(1, 2)  # too-many-function-args\n",
        'TEXT = "# pylint: disable=too-many-function-args"\n',
        '"""\n# pylint: disable=too-many-function-args\n"""\n',
    ],
)
def test_not_a_suppression(tmp_path, source):
    """Other messages, enables, plain comments and pragma-like text in strings are not suppressions."""
    _write(tmp_path, "mod.py", source)

    assert not SourceFile(tmp_path, "mod.py").suppressions


def test_two_messages_in_one_pragma(tmp_path):
    """Each protected message in a pragma is its own suppression."""
    _write(tmp_path, "mod.py", "call(1)  # pylint: disable=too-many-function-args,unexpected-keyword-arg\n")

    assert [found.message for found in SourceFile(tmp_path, "mod.py").suppressions] == [
        "too-many-function-args",
        "unexpected-keyword-arg",
    ]


def test_allowlist(tmp_path):
    """An allowlisted suppression passes; a second one in the same file, or another message, doesn't."""
    _git_init(tmp_path)
    allowed = "call(1)  # pylint: disable=unexpected-keyword-arg\n"
    _write(tmp_path, "allowed.py", allowed)
    _git_add(tmp_path)
    repository = Repository(tmp_path, allowlist={("allowed.py", "unexpected-keyword-arg"): 1})

    assert not repository.violations

    _write(tmp_path, "allowed.py", allowed + "call(2)  # pylint: disable=too-many-function-args\n")
    assert [(found.line, found.message) for found in repository.violations] == [(2, "too-many-function-args")]

    _write(tmp_path, "allowed.py", allowed * 2)
    assert [found.line for found in repository.violations] == [1, 2]


def test_tests_are_checked(tmp_path):
    """Files under ``tests/`` directories are checked too; files git doesn't track are not."""
    _git_init(tmp_path)
    _write(tmp_path, "pkg/tests/test_mod.py", "call(1, 2)  # pylint: disable=too-many-function-args\n")
    _git_add(tmp_path)
    _write(tmp_path, "untracked.py", "call(1, 2)  # pylint: disable=too-many-function-args\n")

    assert [found.path for found in Repository(tmp_path, allowlist={}).violations] == ["pkg/tests/test_mod.py"]


def test_config_disable(tmp_path):
    """Disabling a protected message in pylint's configuration is reported."""
    _write(tmp_path, ".pylintrc", "[MESSAGES CONTROL]\ndisable=too-many-function-args\n")

    assert Repository(tmp_path).disabled_in_config == ["too-many-function-args"]


def test_repository_config_keeps_messages_enabled():
    """This repository's pylint configuration keeps the protected messages enabled."""
    assert not Repository().disabled_in_config


def _comment_action(comment: str) -> str:
    """
    :param comment: A pragma comment from the parametrized cases.
    :return: The pragma's action.
    """
    for action in ("disable-next", "disable-msg"):
        if action in comment:
            return action
    return "disable"


def _git_add(path: Path) -> None:
    """Stage every file under ``path``."""
    subprocess.run(["git", "add", "--all"], cwd=path, check=True)


def _git_init(path: Path) -> None:
    """Make ``path`` a git repository."""
    subprocess.run(["git", "init", "--quiet"], cwd=path, check=True)


def _write(root: Path, path: str, content: str) -> None:
    """
    Write a file, creating its directories.

    :param root: Base directory.
    :param path: File path relative to ``root``.
    :param content: File content.
    """
    (root / path).parent.mkdir(parents=True, exist_ok=True)
    (root / path).write_text(content, encoding="utf-8")
