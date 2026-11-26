"""
Smoke-test an installed infrahouse-toolkit package.

Run it with the package's own interpreter:

    /opt/infrahouse-toolkit/embedded/bin/python3 -I packaging/smoke_test.py

For the macOS tarball, which isn't a Debian package, add ``--no-deb`` (see packaging/smoke-test-macos.sh):

    <unpacked tarball>/bin/python3 -I packaging/smoke_test.py --no-deb

It checks that:

* ``infrahouse_toolkit`` is imported from the interpreter's own tree, not from a source checkout;
* the Debian package is installed for this machine's architecture and has no conffiles (skipped with
  ``--no-deb``);
* every module in the ``infrahouse_toolkit`` package imports;
* every console script is on PATH;
* ``<script> --help`` succeeds when run as a real process, which proves the shebang, the
  interpreter and the entry point work;
* help renders for every subcommand. The command tree is discovered from Click, so new
  commands are covered automatically. Subcommand help is rendered in-process, because Click
  runs parent group callbacks before a subcommand's ``--help`` is parsed, and several of them
  need AWS credentials or required options. That would make the check test the environment
  instead of the package.

Exit code is non-zero if anything fails.
"""

import argparse
import importlib
import os
import pkgutil
import platform
import shutil
import subprocess
import sys
from importlib.metadata import entry_points
from pathlib import Path
from typing import Iterator, List, Tuple

import click

import infrahouse_toolkit

HELP_ENV = {**os.environ, "AWS_DEFAULT_REGION": "us-east-1"}
PACKAGE_NAME = "infrahouse-toolkit"


def check_debian_package() -> List[str]:
    """
    Check the installed Debian package's metadata.

    :return: A list of failures.
    """
    failures = []
    host_arch = subprocess.run(["dpkg", "--print-architecture"], capture_output=True, text=True, check=True).stdout
    package = subprocess.run(
        ["dpkg-query", "--show", "--showformat=${Architecture}\\n${Conffiles}", PACKAGE_NAME],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    package_arch, _, conffiles = package.partition("\n")
    if package_arch != host_arch.strip():
        failures.append(f"{PACKAGE_NAME} is built for {package_arch}, this machine is {host_arch.strip()}")
    if conffiles.strip():
        failures.append(f"{PACKAGE_NAME} has conffiles: {conffiles.strip()}")
    return failures


def check_help() -> Tuple[int, List[str]]:
    """
    Run ``--help`` for every console script and render help for every subcommand.

    :return: The number of commands checked and a list of failures.
    """
    failures = []
    count = 0
    scripts = [ep for ep in entry_points(group="console_scripts") if ep.value.startswith("infrahouse_toolkit.")]
    for ep in sorted(scripts, key=lambda e: e.name):
        executable = shutil.which(ep.name)
        if executable is None:
            failures.append(f"{ep.name}: not on PATH")
            continue
        result = subprocess.run(
            [executable, "--help"], capture_output=True, text=True, env=HELP_ENV, timeout=60, check=False
        )
        if result.returncode != 0:
            last_line = (result.stderr.strip().splitlines() or ["(no output)"])[-1]
            failures.append(f"{ep.name} --help: exit {result.returncode}: {last_line}")
            continue
        root = ep.load()
        for path, ctx in walk(root, click.Context(root, info_name=ep.name)):
            count += 1
            try:
                if not ctx.command.get_help(ctx).strip():
                    failures.append(f"{path} --help: empty help")
            except Exception as err:  # pylint: disable=broad-exception-caught
                failures.append(f"{path} --help: {err!r}")
    return count, failures


def check_imports() -> List[str]:
    """
    Import every non-test module.

    :return: A list of failures.
    """
    failures = []
    for module in pkgutil.walk_packages(infrahouse_toolkit.__path__, prefix="infrahouse_toolkit."):
        if ".tests" in module.name or module.name.endswith("conftest"):
            continue
        try:
            importlib.import_module(module.name)
        except Exception as err:  # pylint: disable=broad-exception-caught
            failures.append(f"import {module.name}: {err!r}")
    return failures


def check_location() -> List[str]:
    """
    Check that ``infrahouse_toolkit`` comes from the interpreter's tree, so the package is what's tested.

    :return: A list of failures.
    """
    module_path = Path(infrahouse_toolkit.__file__).resolve()
    if not module_path.is_relative_to(Path(sys.prefix).resolve()):
        return [f"infrahouse_toolkit is imported from {module_path}, outside {sys.prefix}"]
    return []


def walk(command: click.Command, ctx: click.Context) -> Iterator[Tuple[str, click.Context]]:
    """
    Walk a Click command tree without running any callbacks.

    :param command: The command to start from.
    :param ctx: A context for ``command``.
    :return: (command path, context) for ``command`` and every command under it.
    """
    yield ctx.command_path, ctx
    if isinstance(command, click.Group):
        for name, sub in sorted(command.commands.items()):
            yield from walk(sub, click.Context(sub, info_name=name, parent=ctx))


def main() -> None:
    """Run all checks and report."""
    parser = argparse.ArgumentParser(description="Smoke-test an installed infrahouse-toolkit package.")
    parser.add_argument(
        "--no-deb",
        action="store_true",
        help="Skip the Debian package checks and report the architecture from platform.machine(), "
        "for a package that isn't a .deb, such as the macOS tarball.",
    )
    args = parser.parse_args()

    failures = check_location() + ([] if args.no_deb else check_debian_package()) + check_imports()
    count, help_failures = check_help()
    failures += help_failures
    if args.no_deb:
        arch = platform.machine()
    else:
        arch = subprocess.run(
            ["dpkg", "--print-architecture"], capture_output=True, text=True, check=True
        ).stdout.strip()
    print(f"python {sys.version.split()[0]}, infrahouse-toolkit {infrahouse_toolkit.__version__}, {arch}")
    print(f"commands checked: {count}, failures: {len(failures)}")
    for failure in failures:
        print(f"FAIL {failure}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
