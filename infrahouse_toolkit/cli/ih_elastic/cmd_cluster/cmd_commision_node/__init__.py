"""
.. topic:: ``ih-elastic cluster commission-node``

    A ``ih-elastic cluster commission-node`` subcommand.

    See ``ih-elastic cluster commission-node --help`` for more details.
"""

import json
import sys
from logging import getLogger
from time import sleep

import click
from botocore.exceptions import ClientError
from elasticsearch.client import ClusterClient
from infrahouse_core.aws.asg import ASG
from infrahouse_core.aws.asg_instance import ASGInstance

from infrahouse_toolkit.timeout import timeout

LOG = getLogger()


def wait_until_complete(client: ClusterClient, hook_name: str = None, wait_time: int = 48 * 3600):
    """
    Give up to ``wait_time`` seconds to Elasticsearch to fully join the cluster.

    :param client: a cluster Elasticsearch client.
    :type client: ClusterClient
    :param wait_time: Time in second to wait until the cluster finishes shard relocation.
    :type wait_time: int
    :param hook_name: Lifecycle hook name to extend while waiting.
    :type hook_name: str
    :raise TimeoutError: if after ``wait_time``, Elasticsearch hasn't moved all shards from the node.
    """
    local_instance = ASGInstance()
    asg = ASG(asg_name=local_instance.asg_name)
    if wait_time:
        try:
            with timeout(wait_time):
                while True:
                    health = client.health()
                    LOG.info(
                        "Current cluster state:\n %s",
                        json.dumps(health.body, indent=4),
                    )
                    if health.body["relocating_shards"] == 0:
                        break

                    if hook_name and local_instance.lifecycle_state == "Pending:Wait":
                        LOG.debug("Extend lifecycle hook %s", hook_name)
                        asg.record_lifecycle_action_heartbeat(hook_name=hook_name)

                    sleep(3)
        except TimeoutError as err:
            if hook_name:
                complete_lifecycle_action(hook_name, result="ABANDON")
            LOG.error(err)
            asg.cancel_instance_refresh()
            raise

    else:
        LOG.warning("wait_time = %r, not waiting for Elasticsearch onboard this node.", wait_time)


def complete_lifecycle_action(hook_name, result="CONTINUE"):
    """
    Completes the lifecycle hook.
    If it fails, cancel all instance refreshes in the autoscaling group.
    """
    asg = ASG(asg_name=ASGInstance().asg_name)
    try:
        asg.complete_lifecycle_action(hook_name=hook_name, result=result)

    except ClientError as err:
        LOG.error(err)
        asg.cancel_instance_refresh()
        sys.exit(1)


@click.command(name="commission-node")
@click.option(
    "--wait-until-complete",
    help="Wait this many seconds until Elasticsearch completes moving shards out of this node.",
    default=48 * 3600,
    type=click.INT,
    show_default=True,
)
@click.option(
    "--complete-lifecycle-action",
    help="Complete the lifecycle action when the node is fully provisioned.",
    default=None,
    show_default=True,
)
@click.pass_context
def cmd_commission_node(ctx, **kwargs):
    """
    Ensures the local node fully provisions.When the node is fully operational, optionally
    complete a lifecycle hook.
    """
    hook_name = kwargs["complete_lifecycle_action"]
    wait_time = kwargs["wait_until_complete"]

    client = ClusterClient(ctx.obj["es"])
    health = client.health()

    LOG.info("Checking %s cluster health: %s", health.body["cluster_name"], health.body["status"])
    LOG.debug("Cluster health %s", json.dumps(health.body, indent=4))

    # Trigger re-balancing check
    client.reroute(retry_failed=True)
    wait_until_complete(client, hook_name, wait_time=wait_time)
    if hook_name:
        complete_lifecycle_action(hook_name=hook_name)
