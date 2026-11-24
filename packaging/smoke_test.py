"""
Smoke-test an installed infrahouse-toolkit package.

Run it with the package's own interpreter:

    /opt/infrahouse-toolkit/embedded/bin/python3 packaging/smoke_test.py

It checks that:

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

import importlib
import os
import pkgutil
import shutil
import subprocess
import sys
from importlib.metadata import entry_points

import click

import infrahouse_toolkit

HELP_ENV = {**os.environ, "AWS_DEFAULT_REGION": "us-east-1"}


def check_imports():
    """Import every non-test module; return a list of failures."""
    failures = []
    for module in pkgutil.walk_packages(infrahouse_toolkit.__path__, prefix="infrahouse_toolkit."):
        if ".tests" in module.name or module.name.endswith("conftest"):
            continue
        try:
            importlib.import_module(module.name)
        except Exception as err:  # pylint: disable=broad-exception-caught
            failures.append(f"import {module.name}: {err!r}")
    return failures


def walk(command, ctx):
    """Yield (path, context) for every command in a Click tree, without running callbacks."""
    yield ctx.command_path, ctx
    if isinstance(command, click.Group):
        for name, sub in sorted(command.commands.items()):
            yield from walk(sub, click.Context(sub, info_name=name, parent=ctx))


def check_help():
    """Run --help for every console script and render help for every subcommand."""
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


def main():
    """Run all checks and report."""
    failures = check_imports()
    count, help_failures = check_help()
    failures += help_failures
    print(f"python {sys.version.split()[0]}, infrahouse-toolkit {infrahouse_toolkit.__version__}")
    print(f"commands checked: {count}, failures: {len(failures)}")
    for failure in failures:
        print(f"FAIL {failure}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
