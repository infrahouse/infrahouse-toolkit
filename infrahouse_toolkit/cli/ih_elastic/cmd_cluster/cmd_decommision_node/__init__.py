"""
.. topic:: ``ih-elastic cluster decommission-node``

    A ``ih-elastic cluster decommission-node`` subcommand.

    See ``ih-elastic cluster decommission-node --help`` for more details.
"""

import json
import sys
from logging import getLogger
from time import sleep

import click
from botocore.exceptions import ClientError
from elasticsearch.client import ClusterClient, NodesClient, ShutdownClient
from infrahouse_core.aws.asg import ASG
from infrahouse_core.aws.asg_instance import ASGInstance

from infrahouse_toolkit.lock.exceptions import LockAcquireError
from infrahouse_toolkit.lock.system import SystemLock
from infrahouse_toolkit.timeout import timeout

LOG = getLogger(__name__)


def wait_until_complete(client: ShutdownClient, node_id: str, wait_time: int = 3600, hook_name: str = "terminating"):
    """
    Give up to ``wait_time`` seconds to Elasticsearch to move shards out of the node.
    The function periodically checks the node's shutdown info
    (https://www.elastic.co/guide/en/elasticsearch/reference/current/get-shutdown.html)
    until it's ``COMPLETE``.
    If the node doesn't reach the ``COMPLETE`` state after ``wait_time`` seconds,
    raise TimeoutError.

    :param client: a shutdown Elasticsearch client.
    :type client: ShutdownClient
    :param node_id: Elasticsearch node identifier.
    :type node_id: str
    :param wait_time: Time in second to wait for the ``COMPLETE`` state.
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
                while client.get_node(node_id=node_id).raw["nodes"][0]["status"] != "COMPLETE":
                    LOG.info(
                        "Current shutdown state:\n %s",
                        json.dumps(client.get_node(node_id=node_id).raw, indent=4),
                    )
                    if local_instance.lifecycle_state == "Terminating:Wait":
                        LOG.debug("Extend lifecycle hook %s", hook_name)
                        asg.record_lifecycle_action_heartbeat(hook_name=hook_name)

                    sleep(3)
        except TimeoutError as err:
            LOG.error(err)
            asg.cancel_instance_refresh()
            raise

    else:
        LOG.warning("wait_time = %r, not waiting for Elasticsearch to move shards out of this node.", wait_time)


def complete_lifecycle_action():
    """
    Completes the ``terminating`` lifecycle hook.
    If it fails, cancel all instance refreshes in the autoscaling group.
    """
    asg = ASG(asg_name=ASGInstance().asg_name)
    try:
        asg.complete_lifecycle_action()
    except ClientError as err:
        LOG.error(err)
        asg.cancel_instance_refresh()
        sys.exit(1)


@click.command(name="decommission-node")
@click.option(
    "--only-if-terminating",
    help="Proceed only if the instance is in a 'Terminating:Wait' lifecycle state.",
    default=None,
    is_flag=True,
    show_default=True,
)
@click.option(
    "--wait-until-complete",
    help="Wait this many seconds until Elasticsearch completes moving shards out of this node.",
    default=3600,
    type=click.INT,
    show_default=True,
)
@click.option(
    "--complete-lifecycle-action",
    help="When it's safe, complete the lifecycle action.",
    default=False,
    is_flag=True,
    show_default=True,
)
@click.option(
    "--reason",
    help="Why the node is being decommissioned.",
    default=None,
    required=True,
    show_default=True,
)
@click.argument("node", required=False)
@click.pass_context
def cmd_decommission_node(ctx, **kwargs):
    """
    Prepares a node for decommissioning. Removes shards on of the node
    and can complete a lifecycle hook.

    If the NODE isn't specified, decommission the local node.
    """
    health = ClusterClient(ctx.obj["es"]).health()

    LOG.info("Checking %s cluster health: %s", health.body["cluster_name"], health.body["status"])

    if health.body["status"] != "green":
        LOG.info("The cluster status is %s - not green and, therefore, aborting.", health.body["status"])
        if kwargs["complete_lifecycle_action"]:
            ASG(asg_name=ASGInstance().asg_name).cancel_instance_refresh()
        sys.exit(1)

    node_id = list(NodesClient(ctx.obj["es"]).info(node_id="_local")["nodes"].keys())[0]

    only_if_terminating = kwargs["only_if_terminating"]
    local_instance = ASGInstance()
    shutdown_client = ShutdownClient(ctx.obj["es"])

    LOG.info("Current shutdown state:\n %s", json.dumps(shutdown_client.get_node(node_id=node_id).raw, indent=4))

    if only_if_terminating is None or (only_if_terminating and local_instance.lifecycle_state == "Terminating:Wait"):
        try:
            with SystemLock("/var/tmp/cmd_decommission_node.lock", blocking=False):
                LOG.info("Decommissioning node, %s", node_id)
                shutdown_client.put_node(node_id=node_id, type="remove", reason=kwargs["reason"])
                wait_until_complete(shutdown_client, node_id, wait_time=kwargs["wait_until_complete"])

                if kwargs["complete_lifecycle_action"]:
                    complete_lifecycle_action()

        except LockAcquireError as err:
            LOG.warning(err)
    else:
        LOG.info("No action performed.")
        LOG.info("--only-if-terminating %s", only_if_terminating)
        LOG.info("Lifecycle state: %s", local_instance.lifecycle_state)
