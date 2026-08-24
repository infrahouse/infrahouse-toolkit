"""
.. topic:: ``ih-mysql query-audit status``

    Report what an RDS for MySQL instance is currently logging, and what a
    capture would have to change.

    See ``ih-mysql query-audit status --help`` for more details.
"""

import sys
from logging import getLogger

import click
from botocore.exceptions import ClientError
from tabulate import tabulate

from infrahouse_toolkit.aws.rds import (
    CAPTURE_PARAMETERS,
    RDSError,
    RDSMySQLInstance,
    SlowLogCapture,
)

LOG = getLogger(__name__)


@click.command(name="status")
@click.argument("instance_id")
@click.pass_context
def cmd_status(ctx, instance_id):
    """
    Show the slow query log configuration of a DB instance.

    Read-only.  Run this before a capture to see what will change and whether
    anything stands in the way.
    """
    try:
        instance = RDSMySQLInstance(instance_id, session=ctx.obj["aws_session"])
        group = instance.parameter_group
        capture = SlowLogCapture(instance)
        desired = capture.desired_parameters

        print(f"Instance          : {instance.db_instance_id}")
        print(f"Engine            : {instance.engine} {instance.engine_version}")
        print(f"Status            : {instance.status}")
        print(f"Parameter group   : {group.name} ({group.family})")
        print(f"Attached to       : {', '.join(group.attached_instance_ids)}")
        print(f"CloudWatch exports: {', '.join(instance.cloudwatch_log_exports) or 'none'}")
        print(f"Perf. Insights    : {'enabled' if instance.performance_insights_enabled else 'disabled'}")
        free = instance.free_storage_bytes
        print(f"Free storage      : {f'{free / 1024 ** 3:.1f} GiB' if free is not None else 'unknown'}")
        print()

        rows = []
        for name in CAPTURE_PARAMETERS + ["performance_schema", "slow_query_log_file"]:
            parameter = group.parameters.get(name)
            if parameter is None:
                rows.append([name, "<not in family>", "-", "-", "-"])
                continue
            rows.append(
                [
                    name,
                    parameter.get("ParameterValue"),
                    parameter.get("Source"),
                    parameter.get("ApplyType"),
                    desired.get(name, "-"),
                ]
            )
        print(tabulate(rows, headers=["parameter", "value", "source", "apply", "capture would set"]))
        print()

        _warn_about_findings(instance, group)

    except (RDSError, ClientError) as err:
        LOG.error("%s", err)
        sys.exit(1)


def _warn_about_findings(instance, group) -> None:
    """
    Point out the configurations that quietly break a slow query log audit.

    :param instance: The instance being reported on.
    :type instance: RDSMySQLInstance
    :param group: Its parameter group.
    :type group: RDSParameterGroup
    """
    if group.value_of("log_output") != "FILE":
        LOG.warning(
            "log_output is %s: the slow log goes to the mysql.slow_log table, no log file is produced, "
            "log_slow_extra has no effect, and any CloudWatch slowquery export stays silent.",
            group.value_of("log_output"),
        )
        if "slowquery" in instance.cloudwatch_log_exports:
            LOG.warning(
                "slowquery is in EnabledCloudwatchLogsExports but nothing can be published while "
                "log_output is not FILE."
            )

    long_query_time = group.value_of("long_query_time")
    if long_query_time is None:
        LOG.warning(
            "long_query_time is unset, so the engine default of 10s applies — far too high to see the "
            "cheap, frequent queries an access-pattern audit is about."
        )

    if group.value_of("performance_schema") in ("0", None):
        LOG.warning(
            "performance_schema is off, so events_statements_summary_by_digest is empty and the slow log "
            "is the only source. Turning it on requires a reboot."
        )

    if group.is_default:
        LOG.warning("%s is a default parameter group and cannot be modified.", group.name)

    attached = group.attached_instance_ids
    if len(attached) > 1:
        LOG.warning(
            "Parameter group %s is shared by %d instances (%s). A capture would turn the slow log up "
            "on all of them.",
            group.name,
            len(attached),
            ", ".join(attached),
        )
