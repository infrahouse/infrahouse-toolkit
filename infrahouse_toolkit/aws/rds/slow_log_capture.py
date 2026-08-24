"""
Temporary slow query log capture on an RDS MySQL instance.

Provides :class:`SlowLogCapture` — a context manager that turns the slow query
log all the way up for a bounded window, watches the instance while it fills,
and puts every parameter back the way it found it.

This is the RDS port of the long-standing "collect a slow log for an hour"
shell script.  Two mechanisms change on RDS:

* there is no ``SET GLOBAL`` and no writable ``slow_query_log_file``, so
  everything goes through the DB parameter group;
* ``log_output`` defaults to ``TABLE``, which produces no log file at all, so
  the capture has to flip it to ``FILE`` — and ``log_slow_extra`` only has an
  effect once it does.

.. rubric:: Known limitation: capture coverage cannot be measured

``long_query_time`` is a session variable seeded from the global value when a
connection is made, so connections that predate the change keep the old
threshold.  Percona Server has ``use_global_long_query_time`` to force existing
sessions onto the new value; community MySQL, and therefore RDS for MySQL, does
not.  A pooled client contributes nothing to the capture until its pool
recycles.

This capture cannot tell you how much of the workload that costs it.  It talks
only to the RDS control plane and holds no MySQL credentials, so it cannot run
SQL; and the one place a session's own ``long_query_time`` is visible,
``performance_schema.variables_by_thread``, needs ``performance_schema``, which
is off by default on RDS and static, so enabling it costs a reboot.

The consequence is that an empty capture is ambiguous: an idle instance and a
fully stale connection pool look identical from here.  To tell them apart by
hand, sample ``SHOW GLOBAL STATUS`` before and after the window.  A ``Queries``
delta near zero means the instance was idle.  A non-zero ``Queries`` delta with
no movement in ``Slow_queries`` means the sessions never picked up the new
threshold, and their ratio approximates how much of the traffic did.
"""

import json
import os
import signal
import time
from datetime import datetime, timezone
from logging import getLogger
from typing import Dict, List, Optional

from boto3.session import Session
from botocore.exceptions import ClientError

from infrahouse_toolkit import DEFAULT_OPEN_ENCODING
from infrahouse_toolkit.aws.rds.exceptions import RDSError, SlowLogCaptureError
from infrahouse_toolkit.aws.rds.instance import RDSMySQLInstance
from infrahouse_toolkit.aws.rds.parameter_group import RDSParameterGroup

LOG = getLogger(__name__)

# Every parameter the capture touches, and therefore every parameter it must
# record beforehand and put back afterwards.
CAPTURE_PARAMETERS = [
    "log_output",
    "slow_query_log",
    "long_query_time",
    "log_slow_extra",
    "log_slow_admin_statements",
]

# RDS starts a storage autoscaling event when free space falls below 10% of
# allocated storage (sustained for five minutes, and no more than once every six
# hours).  Autoscaling is not the non-event AWS describes it as, so the capture
# treats that threshold as a floor it must never cross rather than a cushion it
# may spend.  Keeping free space at or above 10% means the first of those three
# conditions is never met.
FREE_STORAGE_RESERVE_RATIO = 0.10

# Ceiling on what one capture may write, so that even a full-size capture
# starting at the reserve cannot push free space under it.  Both ratios are
# taken against *current* allocated storage — the autoscale maximum is headroom
# we are specifically refusing to use.
MAX_LOG_SIZE_RATIO = 0.05

# What a capture writes by default.  The ratio above is a safety ceiling, not a
# working size: 5% of a 2 TiB volume is 100 GiB of slow log, which is a
# download and a pt-query-digest run nobody asked for.  A gigabyte is already
# far more than a query profile needs, and the ceiling still wins on small
# volumes where 5% is less than this.
DEFAULT_MAX_LOG_SIZE = 1024**3


class SlowLogCapture:  # pylint: disable=too-many-instance-attributes
    """
    A bounded slow query log capture on an RDS MySQL instance.

    Used as a context manager::

        with SlowLogCapture(instance) as capture:
            capture.watch(max_run_time=3600, max_log_size=1024**3, min_free_storage=20 * 1024**3)
            paths = capture.download("./audit")

    Leaving the block restores every parameter, whether the block finished,
    raised, or was interrupted.

    :param instance: The instance to capture on.
    :type instance: RDSMySQLInstance
    :param long_query_time: Threshold to log at.  ``0`` logs everything, which
        is the point — a nonzero threshold hides the cheap, frequent queries.
    :type long_query_time: float
    :param log_slow_extra: Whether to record the extra per-query attributes
        (``Rows_examined``, ``Read_*``, ``Tmp_tables``, ...).
    :type log_slow_extra: bool
    :param log_slow_admin_statements: Whether to log admin statements such as
        ``ALTER TABLE``.
    :type log_slow_admin_statements: bool
    :param state_file: Where to record the pre-capture parameter values.
    :type state_file: str
    :param allow_shared_parameter_group: Proceed even when the parameter group
        is attached to more than one instance.
    :type allow_shared_parameter_group: bool
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        instance: RDSMySQLInstance,
        long_query_time: float = 0,
        log_slow_extra: bool = True,
        log_slow_admin_statements: bool = True,
        state_file: str = None,
        allow_shared_parameter_group: bool = False,
    ) -> None:
        self._instance = instance
        self._long_query_time = long_query_time
        self._log_slow_extra = log_slow_extra
        self._log_slow_admin_statements = log_slow_admin_statements
        self._state_file = state_file or f"ih-query-audit-{instance.db_instance_id}.state.json"
        self._allow_shared_parameter_group = allow_shared_parameter_group
        self._snapshot: Optional[List[dict]] = None
        self._baseline: Dict[str, int] = {}
        self._initiated_at: Optional[datetime] = None
        self._started_at: Optional[datetime] = None
        self._previous_sigterm_handler = None

    def __enter__(self) -> "SlowLogCapture":
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        self.stop()
        return False

    # --- Public properties ---

    @property
    def captured_bytes(self) -> int:
        """
        Slow log bytes written since the capture started.

        Measured against a baseline taken at :meth:`start`, so log files that
        were already on the instance do not count toward the size limit.

        :return: Bytes written since the capture started.
        :rtype: int
        """
        total = 0
        for entry in self._instance.slow_log_files:
            total += max(0, entry["size"] - self._baseline.get(entry["name"], 0))
        return total

    @property
    def default_max_log_size(self) -> int:
        """
        What a capture writes unless told otherwise.

        :data:`DEFAULT_MAX_LOG_SIZE`, or :attr:`max_log_size_ceiling` when the
        volume is small enough that the safety ceiling is the lower of the two.

        :return: Bytes.
        :rtype: int
        """
        return min(DEFAULT_MAX_LOG_SIZE, self.max_log_size_ceiling)

    @property
    def default_min_free_storage(self) -> int:
        """
        Free space the capture must leave, as a share of current allocated storage.

        This is RDS's own storage-autoscaling trigger point, not a round number.

        :return: Bytes.
        :rtype: int
        """
        return int(self._instance.allocated_storage_bytes * FREE_STORAGE_RESERVE_RATIO)

    @property
    def desired_parameters(self) -> Dict[str, str]:
        """
        The parameter values this capture will apply.

        :return: Parameter name to value.
        :rtype: Dict[str, str]
        """
        return {
            # RDS defaults log_output to TABLE, which writes to mysql.slow_log
            # instead of a file.  pt-query-digest cannot read that, CloudWatch
            # exports stay silent, and log_slow_extra has no effect there.
            "log_output": "FILE",
            "slow_query_log": "1",
            "long_query_time": self._format_seconds(self._long_query_time),
            "log_slow_extra": "ON" if self._log_slow_extra else "OFF",
            "log_slow_admin_statements": "1" if self._log_slow_admin_statements else "0",
        }

    @property
    def instance(self) -> RDSMySQLInstance:
        """
        :return: The instance being captured on.
        :rtype: RDSMySQLInstance
        """
        return self._instance

    @property
    def max_log_size_ceiling(self) -> int:
        """
        The most one capture may write, whatever the caller asks for.

        A share of current allocated storage, so that a full-size capture
        beginning at the reserve still cannot cross it.

        :return: Bytes.
        :rtype: int
        """
        return int(self._instance.allocated_storage_bytes * MAX_LOG_SIZE_RATIO)

    @property
    def started_at(self) -> Optional[datetime]:
        """
        When queries actually began being logged, which is what bounds the
        window and what ``pt-query-digest --since`` should be given.

        Later than the moment :meth:`start` was called, by however long RDS took
        to report the parameter group in-sync — typically a minute.

        :return: UTC timestamp, or ``None`` before the parameters have landed.
        :rtype: Optional[datetime]
        """
        return self._started_at

    @property
    def state(self) -> dict:
        """
        The payload written to the state file.

        :return: Everything needed to undo the capture from a cold start.
        :rtype: dict
        :raises SlowLogCaptureError: If called before :meth:`start`.
        """
        if self._snapshot is None or self._initiated_at is None:
            raise SlowLogCaptureError("Capture has not started, there is no state to record")
        return {
            "instance_id": self._instance.db_instance_id,
            "parameter_group": self._instance.parameter_group.name,
            # When the change was requested, not when it landed — this file has
            # to be written before the apply, so it cannot know the latter.
            "started_at": self._initiated_at.isoformat(),
            "parameters": self._snapshot,
        }

    @property
    def state_file(self) -> str:
        """
        :return: Path of the file recording pre-capture parameter values.
        :rtype: str
        """
        return self._state_file

    # --- Public methods ---

    def download(self, destination_dir: str) -> List[str]:
        """
        Download every slow log file this capture wrote to.

        Files that grew during the capture are downloaded whole — RDS has no
        way to fetch a byte range — so the returned files may contain queries
        from before the window.  Filter those out downstream with
        ``pt-query-digest --since``, using :attr:`started_at`.

        :param destination_dir: Local directory to write into.
        :type destination_dir: str
        :return: Paths of the downloaded files.
        :rtype: List[str]
        """
        os.makedirs(destination_dir, exist_ok=True)
        paths = []
        for entry in self._instance.slow_log_files:
            if entry["size"] <= self._baseline.get(entry["name"], 0):
                continue
            paths.append(self._instance.download_log_file(entry["name"], destination_dir))
        if not paths:
            LOG.warning("No slow log data was written during the capture window")
        return paths

    def preflight(self, max_log_size: int = None, min_free_storage: int = None) -> None:
        """
        Check that the capture is safe to run before anything is modified.

        Both storage limits default to a share of *current* allocated storage,
        so they mean the same thing on a 10 GiB instance and a 2 TiB one.  An
        absolute default cannot: 20 GiB is nothing on the large volume and more
        than the whole of the small one.

        :param max_log_size: Log bytes the capture may write.  ``None`` for
            :data:`MAX_LOG_SIZE_RATIO` of allocated storage.  A larger explicit
            value is refused rather than clamped.
        :type max_log_size: int
        :param min_free_storage: Free bytes that must remain.  ``None`` for
            :data:`FREE_STORAGE_RESERVE_RATIO` of allocated storage.
        :type min_free_storage: int
        :raises SlowLogCaptureError: If the instance, its parameter group, or
            its free storage make the capture unsafe.
        :raises RDSParameterError: If a parameter cannot be changed immediately.
        """
        if not self._instance.engine.startswith("mysql"):
            raise SlowLogCaptureError(
                f"{self._instance.db_instance_id} runs {self._instance.engine}; this capture supports RDS for MySQL"
            )
        if self._instance.status != "available":
            raise SlowLogCaptureError(f"{self._instance.db_instance_id} is {self._instance.status}, expected available")

        group = self._instance.parameter_group
        if group.is_default:
            raise SlowLogCaptureError(
                f"{self._instance.db_instance_id} uses default parameter group {group.name}, which RDS does not "
                f"allow modifying. Attach a custom parameter group first — that needs a reboot."
            )

        attached = group.attached_instance_ids
        if len(attached) > 1 and not self._allow_shared_parameter_group:
            raise SlowLogCaptureError(
                f"Parameter group {group.name} is attached to {len(attached)} instances "
                f"({', '.join(attached)}). Modifying it would turn the slow log up on all of them. "
                f"Pass allow_shared_parameter_group to proceed anyway."
            )

        group.validate_modifiable(list(self.desired_parameters))

        allocated = self._instance.allocated_storage_bytes
        max_log_size = self.default_max_log_size if max_log_size is None else max_log_size
        min_free_storage = self.default_min_free_storage if min_free_storage is None else min_free_storage

        if max_log_size > self.max_log_size_ceiling:
            raise SlowLogCaptureError(
                f"A {self._as_gib(max_log_size)} log is more than "
                f"{MAX_LOG_SIZE_RATIO:.0%} of {self._as_gib(allocated)} allocated storage on "
                f"{self._instance.db_instance_id}. Cap it at {self._as_gib(self.max_log_size_ceiling)} "
                f"so a full capture cannot push free space under the autoscale threshold."
            )

        free = self._instance.free_storage_bytes
        if free is None:
            raise SlowLogCaptureError(
                "CloudWatch has no recent FreeStorageSpace datapoint for "
                f"{self._instance.db_instance_id}; refusing to fill a volume whose free space cannot be verified"
            )
        if free - max_log_size < min_free_storage:
            raise SlowLogCaptureError(
                f"{self._instance.db_instance_id} has {self._as_gib(free)} free of "
                f"{self._as_gib(allocated)} allocated. A {self._as_gib(max_log_size)} capture would leave "
                f"{self._as_gib(free - max_log_size)}, under the {self._as_gib(min_free_storage)} reserve "
                f"({FREE_STORAGE_RESERVE_RATIO:.0%} of allocated) that keeps RDS from autoextending the volume. "
                f"Free up space, or lower --max-log-size below {self._as_gib(free - min_free_storage)}."
            )

        self._warn_about_cloudwatch_export()
        LOG.info(
            "Preflight passed: %s free of %s allocated, capture capped at %s, reserve %s",
            self._as_gib(free),
            self._as_gib(allocated),
            self._as_gib(max_log_size),
            self._as_gib(min_free_storage),
        )

    def start(self) -> None:
        """
        Record current parameter values, then turn the slow log up.

        The state file is written *before* anything is modified, so a capture
        that dies between the two can still be undone.

        A failure *after* the parameters land rolls itself back: ``__enter__``
        raising means ``__exit__`` never runs, so nothing else would.

        :raises RDSParameterError: If a parameter cannot be changed immediately.
        :raises RDSError: If the change could not be confirmed as applied.
        :raises ClientError: If an RDS API call failed.
        """
        group = self._instance.parameter_group
        self._snapshot = group.snapshot(CAPTURE_PARAMETERS)
        self._initiated_at = datetime.now(timezone.utc)
        # Taken before the parameters land, so files RDS creates on the way to
        # in-sync count as captured rather than as pre-existing.
        self._baseline = {entry["name"]: entry["size"] for entry in self._instance.slow_log_files}

        self._write_state_file()
        self._install_sigterm_handler()

        LOG.info("Previous values: %s", {entry["name"]: entry["value"] for entry in self._snapshot})
        try:
            group.apply(self.desired_parameters)
            self._instance.wait_parameters_in_sync()
        except (ClientError, RDSError):
            LOG.error("Could not start the capture on %s, rolling back", self._instance.db_instance_id)
            self.stop()
            raise

        # The clock starts here, not above: RDS takes a minute or so to report
        # the group in-sync, and nothing is being logged until it does. Stamping
        # this before the apply spends the whole window on that latency.
        self._started_at = datetime.now(timezone.utc)
        LOG.info(
            "Capturing from %s, %ds after the change was requested",
            self._started_at.isoformat(),
            (self._started_at - self._initiated_at).total_seconds(),
        )
        self._warn_about_open_connections()

    def stop(self) -> None:
        """
        Put every parameter back and remove the state file.

        On failure the state file is deliberately left in place so the capture
        can be undone by hand — an instance left at ``long_query_time=0`` will
        keep filling its volume.

        :raises RDSError: If the parameters could not be restored.
        :raises ClientError: If the RDS API call to restore them failed.
        """
        if self._snapshot is None:
            return
        try:
            LOG.info("Restoring parameters on %s", self._instance.db_instance_id)
            self._instance.parameter_group.restore(self._snapshot)
            self._instance.wait_parameters_in_sync()
        except (ClientError, RDSError) as err:
            LOG.error("Failed to restore parameters: %s", err)
            LOG.error("%s IS STILL CAPTURING. Undo it with:", self._instance.db_instance_id)
            LOG.error("    ih-mysql query-audit restore --state-file %s", self._state_file)
            raise
        finally:
            self._snapshot = None
            self._restore_sigterm_handler()

        self._remove_state_file()
        LOG.info("Parameters restored on %s", self._instance.db_instance_id)

    def watch(
        self,
        max_run_time: int,
        max_log_size: int,
        min_free_storage: int,
        poll_interval: int = 30,
    ) -> str:
        """
        Block until a stop condition is met.

        Stops on whichever comes first: the time limit, the log size limit, or
        free storage dropping to the reserve.  The storage check is the one
        that matters — RDS log files share the data volume, and a full volume
        takes the instance down.

        :param max_run_time: Maximum capture duration in seconds.
        :type max_run_time: int
        :param max_log_size: Maximum slow log bytes to write.
        :type max_log_size: int
        :param min_free_storage: Stop if free storage drops below this many bytes.
        :type min_free_storage: int
        :param poll_interval: Seconds between checks.
        :type poll_interval: int
        :return: Which limit ended the capture.
        :rtype: str
        """
        if self._started_at is None:
            raise SlowLogCaptureError("Capture has not started, there is nothing to watch")

        deadline = self._started_at.timestamp() + max_run_time
        while True:
            captured = self.captured_bytes
            free = self._instance.free_storage_bytes
            remaining = int(deadline - datetime.now(timezone.utc).timestamp())
            LOG.info(
                "Captured %s, %s free, %ds remaining",
                self._as_gib(captured),
                self._as_gib(free) if free is not None else "unknown",
                max(0, remaining),
            )

            if captured >= max_log_size:
                return f"log size limit reached ({self._as_gib(captured)})"
            if free is not None and free <= min_free_storage:
                return f"free storage dropped to {self._as_gib(free)}"
            if remaining <= 0:
                return f"time limit reached ({max_run_time}s)"

            time.sleep(min(poll_interval, max(1, remaining)))

    @classmethod
    def restore_from_state_file(cls, state_file: str, session: Session) -> str:
        """
        Undo a capture from its state file, without the original process.

        :param state_file: Path to the state file written by :meth:`start`.
        :type state_file: str
        :param session: Authenticated boto3 session.
        :type session: Session
        :return: Identifier of the instance that was restored.
        :rtype: str
        :raises SlowLogCaptureError: If the state file is unusable.
        """
        try:
            with open(state_file, encoding=DEFAULT_OPEN_ENCODING) as descriptor:
                state = json.load(descriptor)
        except json.JSONDecodeError as err:
            raise SlowLogCaptureError(f"{state_file} is not valid JSON: {err}") from err

        try:
            group_name = state["parameter_group"]
            instance_id = state["instance_id"]
            parameters = state["parameters"]
        except KeyError as err:
            raise SlowLogCaptureError(f"{state_file} is missing key {err}") from err

        LOG.info("Restoring %s from %s", instance_id, state_file)
        RDSParameterGroup(group_name, session=session).restore(parameters)
        RDSMySQLInstance(instance_id, session=session).wait_parameters_in_sync()
        os.remove(state_file)
        return instance_id

    # --- Private methods ---

    @staticmethod
    def _as_gib(size: int) -> str:
        """
        :param size: Size in bytes.
        :type size: int
        :return: Human-readable size.
        :rtype: str
        """
        return f"{size / 1024 ** 3:.2f} GiB"

    @staticmethod
    def _format_seconds(value: float) -> str:
        """
        Render a seconds value the same way whatever numeric type it arrives as.

        Click hands ``capture`` a float, so ``0`` becomes ``0.0`` while the
        constructor default stays ``0`` — enough to make ``capture`` and
        ``status`` disagree about the same setting.  Fixed decimal notation is
        used rather than ``str()`` because ``str(0.000001)`` is ``1e-06``, and
        six places is exactly MySQL's microsecond resolution.

        :param value: Seconds.
        :type value: float
        :return: The value without a scientific-notation or trailing-zero tail.
        :rtype: str
        """
        return f"{float(value):.6f}".rstrip("0").rstrip(".")

    def _install_sigterm_handler(self) -> None:
        """
        Turn SIGTERM into SystemExit so the context manager still unwinds.

        SIGINT already raises KeyboardInterrupt; SIGTERM would otherwise kill
        the process with the instance still capturing.
        """

        def handler(signum, frame):  # pylint: disable=unused-argument
            raise SystemExit(f"Received signal {signum}, stopping the capture")

        self._previous_sigterm_handler = signal.signal(signal.SIGTERM, handler)

    def _remove_state_file(self) -> None:
        """Delete the state file once the capture has been undone."""
        if os.path.exists(self._state_file):
            os.remove(self._state_file)

    def _restore_sigterm_handler(self) -> None:
        """Put the previous SIGTERM handler back."""
        if self._previous_sigterm_handler is not None:
            signal.signal(signal.SIGTERM, self._previous_sigterm_handler)
            self._previous_sigterm_handler = None

    def _warn_about_cloudwatch_export(self) -> None:
        """
        Warn when flipping ``log_output`` will wake a dormant CloudWatch export.

        RDS publishes the slow log *file*, so an instance configured with
        ``slowquery`` in its exports but ``log_output=TABLE`` has been shipping
        nothing.  Setting ``log_output=FILE`` starts that export for the
        duration of the capture — a useful durable copy, and a billable one.
        """
        if "slowquery" not in self._instance.cloudwatch_log_exports:
            return
        if self._instance.parameter_group.value_of("log_output") == "FILE":
            return
        LOG.warning(
            "slowquery is in EnabledCloudwatchLogsExports but log_output is not FILE, so nothing has been "
            "published so far. This capture starts that export, and CloudWatch Logs ingestion is billable."
        )

    def _warn_about_open_connections(self) -> None:
        """
        Warn that connections opened before the change keep the old threshold.

        ``long_query_time`` is a session variable seeded from the global value
        at connect time.  Percona Server has ``use_global_long_query_time`` to
        force existing sessions to pick up the new value; community MySQL, and
        therefore RDS for MySQL, does not.  On a pooled application the capture
        sees nothing from established connections until the pool recycles.
        """
        LOG.warning(
            "Connections opened before this change keep their old long_query_time — "
            "MySQL seeds it per session at connect time and has no equivalent of Percona's "
            "use_global_long_query_time. Pooled clients will not appear until the pool recycles."
        )
        if self._instance.parameter_group.value_of("performance_schema") in ("0", None):
            LOG.warning(
                "performance_schema is off, so the number of sessions still on the old "
                "threshold cannot be measured. Enabling it needs a reboot (it is a static parameter)."
            )

    def _write_state_file(self) -> None:
        """
        Persist pre-capture parameter values.

        :raises SlowLogCaptureError: If the state file cannot be written.
        """
        try:
            with open(self._state_file, "w", encoding=DEFAULT_OPEN_ENCODING) as descriptor:
                json.dump(self.state, descriptor, indent=4)
        except OSError as err:
            raise SlowLogCaptureError(f"Cannot write state file {self._state_file}: {err}") from err
        LOG.info("Recorded pre-capture parameters in %s", self._state_file)
