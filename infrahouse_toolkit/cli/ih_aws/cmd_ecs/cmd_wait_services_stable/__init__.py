"""
.. topic:: ``ih-aws ecs``

    A ``ih-aws ecs`` subcommand.

    See ``ih-aws ecs --help`` for more details.
"""

import sys
import time
from logging import getLogger

import click
from botocore.exceptions import ClientError

from infrahouse_toolkit.aws import get_aws_client

LOG = getLogger(__name__)


@click.command(name="wait-services-stable")
@click.option("--cluster", help="ECS cluster name that runs requested services.", required=True)
@click.option(
    "--service",
    help="ECS service name that we wait to become stable. Multiple services can be specified.",
    required=True,
    multiple=True,
)
@click.option(
    "--wait-timeout",
    help="Time in seconds to wait until all services become stable.",
    default=20 * 60,
    show_default=True,
)
@click.pass_context
def cmd_wait_services_stable(ctx, **kwargs):
    """
    Wait up to --timeout seconds until all specified services in an ECS cluster
    become stable.

    The service is considered stable when there is only one deployment for it
    and number of running tasks is equal to desired number tasks.
    """
    aws_config = ctx.obj["aws_config"]
    aws_profile = ctx.obj["aws_profile"]
    cluster = kwargs["cluster"]
    services = kwargs["service"]
    wait_timeout = kwargs["wait_timeout"]
    try:
        aws_session = ctx.obj["aws_session"]
        response = get_aws_client(
            "sts", aws_profile, aws_config.get_region(aws_profile), session=aws_session
        ).get_caller_identity()
        LOG.debug("Connected to AWS as %s", response["Arn"])
        ecs_client = get_aws_client("ecs", aws_profile, aws_config.get_region(aws_profile), session=aws_session)
        now = time.time()
        _wait_for_services(ecs_client, cluster, services, start_time=now, end_time=now + wait_timeout)

    except ClientError as err:
        LOG.exception(err)
        LOG.error("Try to run ih-aws with --aws-profile option.")
        LOG.error("Available profiles:\n\t%s", "\n\t".join(aws_config.profiles))
        sys.exit(1)


def _wait_for_services(ecs_client, cluster, services, start_time, end_time):
    sleep_time = 15
    while time.time() < end_time:
        response = ecs_client.describe_services(cluster=cluster, services=list(services))

        all_services_stable = True
        for service in response["services"]:
            n_deployments = len(service["deployments"])
            LOG.info("Service: %s, deployments = %d", service["serviceName"], n_deployments)

            for deployment in service["deployments"]:
                LOG.info(
                    "Service: %s, deployment = %s (%s), running = %d, desired = %s",
                    service["serviceName"],
                    deployment["id"],
                    deployment["status"],
                    deployment["runningCount"],
                    deployment["desiredCount"],
                )
                if deployment["runningCount"] != deployment["desiredCount"]:
                    all_services_stable = False

            if n_deployments != 1:
                all_services_stable = False

        if all_services_stable:
            LOG.info("Services %s are stable", ",".join(services))
            sys.exit(0)
        else:
            LOG.info("Services are not stable yet. Waiting %s seconds", sleep_time)
            time.sleep(sleep_time)

    LOG.error("Services %s didn't become stable after %s seconds", ",".join(services), end_time - start_time)
    sys.exit(1)
