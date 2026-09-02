"""
.. topic:: ``ih-skeema run``

    A ``ih-skeema run`` subcommand.

    See ``ih-skeema run --help`` for more details.
"""

import logging
import sys
from os import defpath, environ
from subprocess import Popen

import click

from infrahouse_toolkit.cli.ih_skeema.defaults_file import (
    DEFAULTS_FILE_VARIABLE,
    mysql_defaults_file,
)

LOG = logging.getLogger()

SKEEMA_COMMANDS = [
    "add-environment",
    "diff",
    "format",
    "help",
    "init",
    "lint",
    "pull",
    "push",
    "version",
]


@click.command(
    name="run",
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
@click.argument("skeema_command", type=click.Choice(SKEEMA_COMMANDS))
@click.pass_context
def cmd_run(ctx, *args, **kwargs):
    """
    Run a skeema command.
    """
    LOG.debug("args = %s", args)
    LOG.debug("kwargs = %s", kwargs)
    LOG.debug(ctx.args)
    cmd = [ctx.obj["skeema_path"], "--user", ctx.obj["username"], kwargs["skeema_command"]]
    cmd.extend(ctx.args)
    try:
        with mysql_defaults_file(ctx.obj["username"], ctx.obj["password"]) as defaults_path:
            env = {
                "MYSQL_PWD": ctx.obj["password"],
                DEFAULTS_FILE_VARIABLE: defaults_path,
                # pt-online-schema-change is #!/usr/bin/env perl and needs a PATH.
                "PATH": environ.get("PATH", defpath),
            }
            with Popen(cmd, env=env) as proc:
                LOG.info("Launched command: %s", " ".join(cmd))
                proc.communicate()
                sys.exit(proc.returncode)

    except FileNotFoundError as err:
        LOG.error("Command `%s` failed to start.", " ".join(cmd))
        LOG.error("Please install Skeema first or specify a skeema executable via --skeema-path.")
        LOG.exception(err)
        sys.exit(1)
