"""
.. topic:: ``ih-puppet``

    A group of commands to work with Puppet.

    See ``ih-puppet --help`` for more details.
"""

from logging import getLogger

import click
from infrahouse_core.logging import setup_logging

from infrahouse_toolkit.cli.ih_puppet.cmd_apply import cmd_apply

LOG = getLogger()


@click.group()
@click.option(
    "--debug",
    help="Enable debug logging.",
    is_flag=True,
    default=False,
    show_default=True,
)
@click.option(
    "--quiet",
    help="Suppress informational messages and output only warnings and errors.",
    is_flag=True,
    default=False,
    show_default=True,
)
@click.option(
    "--environment",
    help="Puppet environment",
    default="production",
    show_default=True,
)
@click.option(
    "--environmentpath",
    help="A path for directory environments.",
    default="{root_directory}/environments",
    show_default=True,
)
@click.option(
    "--root-directory",
    help="Path where the puppet code is hosted. "
    "The directory must include subdirectories ``environments``, ``modules``.",
    default="/opt/puppet-code",
    show_default=True,
)
@click.option(
    "--hiera-config",
    help="Path to hiera configuration file.",
    default="{root_directory}/environments/{environment}/hiera.yaml",
    show_default=True,
)
@click.option(
    "--module-path",
    help="Path to common puppet modules.",
    default="{root_directory}/modules",
    show_default=True,
)
@click.option(
    "--cancel-instance-refresh-on-error",
    help="If ih-puppet fails, try to cancel all existing autoscaling group instance refreshes.",
    is_flag=True,
    default=False,
    show_default=True,
)
@click.version_option()
@click.pass_context
def ih_puppet(ctx, **kwargs):
    """Puppet wrapper."""
    setup_logging(debug=kwargs["debug"], quiet=kwargs["quiet"])
    ctx.obj = {
        "debug": kwargs["debug"],
        "quiet": kwargs["quiet"],
        "environment": kwargs["environment"],
        "root_directory": kwargs["root_directory"],
        "hiera_config": kwargs["hiera_config"].format(
            root_directory=kwargs["root_directory"],
            environment=kwargs["environment"],
        ),
        "environmentpath": kwargs["environmentpath"].format(root_directory=kwargs["root_directory"]),
        "module_path": kwargs["module_path"].format(
            root_directory=kwargs["root_directory"],
            environment=kwargs["environment"],
        ),
        "cancel_instance_refresh_on_error": kwargs["cancel_instance_refresh_on_error"],
    }


for cmd in [cmd_apply]:
    # noinspection PyTypeChecker
    ih_puppet.add_command(cmd)
