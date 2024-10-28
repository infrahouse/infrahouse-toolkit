"""
.. topic:: ``ih-github runner check-health``

    A ``ih-github runner check-health`` subcommand.

    See ``ih-github runner check-health --help`` for more details.
"""

import logging
import sys
import subprocess
from shutil import disk_usage

import click

from infrahouse_toolkit.aws.asg_instance import ASGInstance

LOG = logging.getLogger()


@click.command(
    name="check-health",
)
def cmd_check_health():
    """
    Check if runner is online and healthy. If not healthy, make the instance as Unhealthy
    in the autoscaling group.

    Exit code is zero if healthy. Otherwise, 1.
    """
    for check in [_disk_usage, _check_is_service_running]:
        if not check():
            ASGInstance().mark_unhealthy()
            sys.exit(1)


def _disk_usage(path="/", threshold=99.0) -> bool:
    stat = disk_usage(path)
    du_pct = 100 * stat.used / stat.total
    if du_pct > threshold:
        LOG.error("Disk usage on partition %s is %f%%, more than threshold %f%%", path, du_pct, threshold)
        return False
    LOG.debug("Disk usage on partition %s is %f%%", path, du_pct)
    return True


def _check_is_service_running(service_name="actions-runner") -> bool:
    try:
        output = subprocess.run(
            ["systemctl", "is-active", service_name],
            capture_output=True,
            text=True
        )
        # If the service is active, output will contain 'active'
        return output.stdout.strip() == "active"
    except Exception as e:
        print(f"Error checking service status: {e}")
        return False
