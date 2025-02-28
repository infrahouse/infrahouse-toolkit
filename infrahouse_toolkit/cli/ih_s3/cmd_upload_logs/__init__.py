"""
.. topic:: ``ih-s3 upload-logs``

    A ``ih-s3 upload-logs`` subcommand.

    See ``ih-s3 upload-logs`` for more details.
"""

import sys
from logging import getLogger
from subprocess import PIPE, Popen
from urllib.parse import urlparse

import click
from botocore.exceptions import ClientError
from infrahouse_core.aws.asg import ASG
from infrahouse_core.aws.asg_instance import ASGInstance

from infrahouse_toolkit.lock.exceptions import LockAcquireError
from infrahouse_toolkit.lock.system import SystemLock

LOG = getLogger()


def normalize_directory_name(source: str) -> str:
    """
    Remove slashes and dots from ends for the path and replace slashes with dashes.

    :param source: original path name.
    :return: modified path name.
    """
    return source.lstrip("/.").replace("/", "-")


@click.command(name="upload-logs")
@click.option(
    "--only-if-terminating",
    help="Proceed only if the instance is in a 'Terminating:Wait' lifecycle state.",
    default=None,
    is_flag=True,
    show_default=True,
)
@click.option(
    "--wait-until-complete",
    help="Wait this many seconds until the logs are uploaded.",
    default=3600,
    type=click.INT,
    show_default=True,
)
@click.option(
    "--complete-lifecycle-action",
    help="Specify a lifecycle hook name to complete it.",
    default=None,
    show_default=True,
)
@click.argument("local_directory")
@click.argument("s3_path")
@click.pass_context
def cmd_upload_logs(ctx, **kwargs):
    """
    Archive the local directory and upload it to S3.
    For example, a command

    \b
    ih-s3 upload-logs /var/log s3://foo-bucket/path/to/

    will create an S3 object s3://foo-bucket/path/to/var-log.tar.gz
    """
    s3_client = ctx.obj["s3_client"]
    url_parts = urlparse(kwargs["s3_path"])
    local_instance = ASGInstance()
    only_if_terminating = kwargs["only_if_terminating"]

    if only_if_terminating is None or (only_if_terminating and local_instance.lifecycle_state == "Terminating:Wait"):
        try:
            with SystemLock("/var/tmp/cmd_upload_logs.lock", blocking=False):
                try:
                    cmd = ["tar", "zcf", "-", kwargs["local_directory"]]
                    with Popen(cmd, stdout=PIPE) as proc:
                        s3_client.upload_fileobj(
                            proc.stdout,
                            url_parts.netloc,
                            f"{url_parts.path.strip('/')}/{normalize_directory_name(kwargs['local_directory'])}.tar.gz",
                        )
                except ClientError as err:
                    LOG.exception(err)
                    sys.exit(1)
                if kwargs["complete_lifecycle_action"]:
                    ASG(asg_name=local_instance.asg_name).complete_lifecycle_action(kwargs["complete_lifecycle_action"])

        except LockAcquireError as err:
            LOG.warning(err)
