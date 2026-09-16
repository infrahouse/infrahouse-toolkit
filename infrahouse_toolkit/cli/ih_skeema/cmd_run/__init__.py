"""
.. topic:: ``ih-skeema run``

    A ``ih-skeema run`` subcommand.

    See ``ih-skeema run --help`` for more details.
"""

import logging
import sys
from subprocess import Popen

import click

from infrahouse_toolkit.skeema import EXIT_ERROR, SkeemaError

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
@click.option(
    "--expect-digest",
    help="Push only if the pending changes still have this digest, as reported by ih-skeema preflight. "
    "This detects a change since approval; it doesn't pin the changes, because the push works "
    "out the diff again when it runs.",
    default=None,
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
    skeema = ctx.obj["skeema"]
    if kwargs["expect_digest"]:
        if kwargs["skeema_command"] != "push":
            raise click.UsageError("--expect-digest only applies to push.")
        try:
            skeema.diff(ctx.args).verify_digest(kwargs["expect_digest"])
            LOG.info("The pending changes match digest %s.", kwargs["expect_digest"])
        except SkeemaError as err:
            LOG.error("%s", err)
            sys.exit(EXIT_ERROR)

    cmd = skeema.command(kwargs["skeema_command"], ctx.args)
    try:
        with skeema.environment() as env:
            with Popen(cmd, env=env) as proc:
                LOG.info("Launched command: %s", " ".join(cmd))
                proc.communicate()
                sys.exit(proc.returncode)

    except SkeemaError as err:
        LOG.error("%s", err)
        sys.exit(EXIT_ERROR)

    except FileNotFoundError as err:
        LOG.error("Command `%s` failed to start.", " ".join(cmd))
        LOG.error("Please install Skeema first or specify a skeema executable via --skeema-path.")
        LOG.exception(err)
        sys.exit(1)
