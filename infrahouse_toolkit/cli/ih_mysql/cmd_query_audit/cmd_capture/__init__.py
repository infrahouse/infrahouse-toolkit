"""
.. topic:: ``ih-mysql query-audit capture``

    Turn the slow query log all the way up on an RDS for MySQL instance for a
    bounded window, download what it wrote, put every parameter back, and
    digest the result.

    See ``ih-mysql query-audit capture --help`` for more details.
"""

import sys
from datetime import datetime, timezone
from logging import getLogger
from os import makedirs
from os import path as osp

import click
from botocore.exceptions import ClientError
from tabulate import tabulate

from infrahouse_toolkit.aws.rds import (
    CAPTURE_PARAMETERS,
    QueryDigest,
    QueryDigestError,
    RDSError,
    SlowLogCapture,
)
from infrahouse_toolkit.aws.rds.query_digest import PT_QUERY_DIGEST
from infrahouse_toolkit.cli.ih_mysql.cmd_query_audit.instance_list import InstanceList
from infrahouse_toolkit.cli.utils import check_dependencies

LOG = getLogger(__name__)

# The three cuts the profile needs: what costs the most time, what reads the
# most rows, and how that splits per table.
DIGEST_REPORTS = [
    {"name": "digest-by-query-time.txt", "group_by": "fingerprint", "order_by": "Query_time:sum"},
    {"name": "digest-by-rows-examined.txt", "group_by": "fingerprint", "order_by": "Rows_examined:sum"},
    {"name": "digest-by-table.txt", "group_by": "tables", "order_by": "Query_time:sum"},
]


@click.command(name="capture")
@click.option(
    "--long-query-time",
    help="Threshold to log at, in seconds. Zero logs everything, which is the point of an audit — "
    "a nonzero threshold systematically hides the cheap, frequent queries.",
    type=float,
    default=0,
    show_default=True,
)
@click.option(
    "--max-run-time",
    help="Stop after this many hours.",
    type=float,
    default=1.0,
    show_default=True,
)
@click.option(
    "--max-log-size",
    help="Stop after the capture has written this many megabytes of slow log. Defaults to 1024, or 5% of "
    "the instance's current allocated storage when that is smaller. 5% is a hard ceiling — a larger value "
    "is refused, because a full-size capture must not push free storage under the reserve.",
    type=int,
    default=None,
)
@click.option(
    "--min-free-storage",
    help="Stop if instance free storage drops to this many gigabytes. Defaults to 10% of the instance's "
    "current allocated storage, which is the point where RDS starts autoextending the volume. Log files "
    "live on the data volume, so this is what keeps a capture from provoking that.",
    type=int,
    default=None,
)
@click.option(
    "--poll-interval",
    help="Seconds between watchdog checks.",
    type=int,
    default=30,
    show_default=True,
)
@click.option(
    "--output-dir",
    help="Directory for downloaded logs and reports. Defaults to a timestamped directory in the "
    "current working directory.",
    default=None,
)
@click.option(
    "--state-file",
    help="Where to record pre-capture parameter values. Defaults to restore-state.json in the output directory.",
    default=None,
)
@click.option(
    "--slow-extra/--no-slow-extra",
    help="Record the extra per-query attributes (Rows_examined, Read_*, Tmp_tables).",
    default=True,
    show_default=True,
)
@click.option(
    "--admin-statements/--no-admin-statements",
    help="Log admin statements such as ALTER TABLE.",
    default=True,
    show_default=True,
)
@click.option(
    "--allow-shared-parameter-group",
    help="Proceed even when the parameter group is attached to more than one instance. This turns the "
    "slow log up on every one of them.",
    is_flag=True,
    default=False,
)
@click.option(
    "--digest/--no-digest",
    help="Run pt-query-digest on the downloaded logs.",
    default=True,
    show_default=True,
)
@click.option(
    "--dry-run",
    help="Run the preflight checks and print the plan without changing anything.",
    is_flag=True,
    default=False,
)
@click.option(
    "--yes",
    "-y",
    help="Do not ask for confirmation.",
    is_flag=True,
    default=False,
)
@click.argument("instance_id", required=False)
@click.pass_context
def cmd_capture(ctx, **kwargs):  # pylint: disable=too-many-locals
    """
    Capture and digest the slow query log of a DB instance.

    \b
    The capture:
      1. records every parameter it is about to change, to a state file;
      2. sets log_output=FILE, slow_query_log=1, long_query_time and friends;
      3. watches time, log size and free storage until a limit is hit;
      4. restores every parameter to exactly what it found;
      5. downloads what was written and runs pt-query-digest over it.

    Parameters are restored on interrupt and on error too. If restoring itself
    fails, the state file is left behind — undo it with
    ``ih-mysql query-audit restore --state-file``.

    Omitting INSTANCE_ID lists the MySQL instances in the region.

    \b
    Known limitation: connections opened before the change keep their old
    long_query_time, and this command cannot measure how many. It holds no
    MySQL credentials, and performance_schema — the only place a session's
    own threshold is visible — is off by default on RDS. So an empty capture
    cannot be told apart from an idle instance from here. Compare the Queries
    and Slow_queries counters in SHOW GLOBAL STATUS across the window to tell
    which it was.
    """
    max_run_time = int(kwargs["max_run_time"] * 3600)
    # Left as None so the capture can size them against the instance's own
    # allocated storage; a flat default cannot suit both a 10 GiB and a 2 TiB volume.
    max_log_size = None if kwargs["max_log_size"] is None else kwargs["max_log_size"] * 1024**2
    min_free_storage = None if kwargs["min_free_storage"] is None else kwargs["min_free_storage"] * 1024**3

    try:
        session = ctx.obj["aws_session"]
        instance = InstanceList(session, region=ctx.obj["aws_region"]).require(kwargs["instance_id"])
        instance_id = instance.db_instance_id
        output_dir = kwargs["output_dir"] or _default_output_dir(instance_id)
        state_file = kwargs["state_file"] or osp.join(output_dir, "restore-state.json")
        makedirs(output_dir, exist_ok=True)
        capture = SlowLogCapture(
            instance,
            long_query_time=kwargs["long_query_time"],
            log_slow_extra=kwargs["slow_extra"],
            log_slow_admin_statements=kwargs["admin_statements"],
            state_file=state_file,
            allow_shared_parameter_group=kwargs["allow_shared_parameter_group"],
        )

        # Fail on a missing pt-query-digest now, not after an hour of capturing.
        if kwargs["digest"]:
            check_dependencies([PT_QUERY_DIGEST])

        # Size the storage limits against this instance before they are used for
        # the plan, the preflight and the watchdog alike.
        max_log_size = capture.default_max_log_size if max_log_size is None else max_log_size
        min_free_storage = capture.default_min_free_storage if min_free_storage is None else min_free_storage

        capture.preflight(max_log_size=max_log_size, min_free_storage=min_free_storage)
        _print_plan(capture, max_run_time, max_log_size, min_free_storage, output_dir)

        if kwargs["dry_run"]:
            LOG.info("Dry run: nothing was changed")
            sys.exit(0)

        if not kwargs["yes"]:
            click.confirm(
                f"Turn the slow query log up on {instance_id} for up to {kwargs['max_run_time']}h?",
                abort=True,
            )

        with capture:
            try:
                reason = capture.watch(
                    max_run_time=max_run_time,
                    max_log_size=max_log_size,
                    min_free_storage=min_free_storage,
                    poll_interval=kwargs["poll_interval"],
                )
            except KeyboardInterrupt:
                reason = "interrupted"
        LOG.info("Capture finished: %s", reason)

        digest = QueryDigest(capture.download(output_dir), since=capture.started_at)
        events = digest.event_count
        if not events:
            LOG.error(
                "No queries were logged during the capture window. RDS writes a log file header even "
                "when nothing is captured, so an empty capture still produces a file."
            )
            LOG.error(
                "Connections opened before the change keep their old long_query_time. Give the client "
                "pool time to recycle, or capture for longer."
            )
            sys.exit(1)
        LOG.info("Captured %d queries", events)

        reports = _run_digests(digest, output_dir) if kwargs["digest"] else []
        _print_summary(output_dir, digest.log_files, reports)

    except click.Abort:
        LOG.info("Aborted, nothing was changed")
        sys.exit(1)
    except (RDSError, QueryDigestError, ClientError) as err:
        LOG.error("%s", err)
        sys.exit(1)


def _default_output_dir(instance_id: str) -> str:
    """
    :param instance_id: DB instance identifier.
    :type instance_id: str
    :return: A timestamped directory name for this capture.
    :rtype: str
    """
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    return f"query-audit-{instance_id}-{stamp}"


def _print_plan(capture, max_run_time, max_log_size, min_free_storage, output_dir) -> None:
    """
    Print what the capture will change and what will stop it.

    :param capture: The configured capture.
    :type capture: SlowLogCapture
    :param max_run_time: Time limit in seconds.
    :type max_run_time: int
    :param max_log_size: Log size limit in bytes.
    :type max_log_size: int
    :param min_free_storage: Free storage floor in bytes.
    :type min_free_storage: int
    :param output_dir: Directory results are written to.
    :type output_dir: str
    """
    group = capture.instance.parameter_group
    desired = capture.desired_parameters
    rows = [
        [name, group.value_of(name), group.parameters[name].get("Source"), desired[name]] for name in CAPTURE_PARAMETERS
    ]
    gib = 1024**3
    instance = capture.instance
    allocated = instance.allocated_storage_bytes
    free = instance.free_storage_bytes

    print(f"\nParameter group {group.name} on {instance.db_instance_id}:\n")
    print(tabulate(rows, headers=["parameter", "current", "source", "capture sets"]))
    print(
        f"\nStorage : {free / gib:.1f} GiB free of {allocated / gib:.0f} GiB allocated. "
        f"Capture writes at most {max_log_size / gib:.1f} GiB, leaving "
        f"{(free - max_log_size) / gib:.1f} GiB against a {min_free_storage / gib:.1f} GiB reserve."
    )
    print(
        f"          The reserve is RDS's autoextend trigger — staying above it means the volume "
        f"is never grown{_autoscaling_note(instance)}."
    )
    print(
        f"\nStops at: {max_run_time}s, or {max_log_size / 1024 ** 2:.0f} MiB of slow log, "
        f"or {min_free_storage / gib:.1f} GiB free storage remaining."
    )
    print(f"Output  : {output_dir}")
    print(f"Undo    : ih-mysql query-audit restore --state-file {capture.state_file}\n")


def _autoscaling_note(instance) -> str:
    """
    Describe the autoextend ceiling the capture is staying clear of.

    :param instance: The instance being captured on.
    :type instance: RDSMySQLInstance
    :return: A clause naming the threshold, or an empty string when storage
        autoscaling is off.
    :rtype: str
    """
    ceiling = instance.max_allocated_storage_bytes
    if ceiling is None:
        return " (autoscaling is off, so a full volume would be an outage)"
    return f" (autoscaling is on, up to {ceiling / 1024 ** 3:.0f} GiB — deliberately unused)"


def _print_summary(output_dir, log_files, reports) -> None:
    """
    Print where everything landed.

    :param output_dir: Directory results were written to.
    :type output_dir: str
    :param log_files: Downloaded slow log files.
    :type log_files: list
    :param reports: Generated digest reports.
    :type reports: list
    """
    total = sum(osp.getsize(path) for path in log_files)
    print(f"\nCaptured {total / 1024 ** 2:.1f} MiB across {len(log_files)} log file(s) in {output_dir}:")
    for path in log_files:
        print(f"  {path}")
    for path in reports:
        print(f"  {path}")


def _run_digests(digest, output_dir) -> list:
    """
    Run the standard set of pt-query-digest reports over a capture.

    :param digest: The capture's log files, already scoped to the window.
    :type digest: QueryDigest
    :param output_dir: Directory to write reports into.
    :type output_dir: str
    :return: Paths of the generated reports.
    :rtype: list
    """
    paths = []
    for report in DIGEST_REPORTS:
        paths.append(
            digest.report(
                osp.join(output_dir, report["name"]),
                group_by=report["group_by"],
                order_by=report["order_by"],
            )
        )
    return paths
