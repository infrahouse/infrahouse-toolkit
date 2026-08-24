"""Tests for :class:`infrahouse_toolkit.aws.rds.SlowLogCapture`."""

import json
from os import path as osp
from unittest.mock import MagicMock, patch

import pytest

from infrahouse_toolkit.aws.rds import (
    CAPTURE_PARAMETERS,
    RDSError,
    RDSMySQLInstance,
    RDSParameterError,
    RDSParameterGroup,
    SlowLogCapture,
    SlowLogCaptureError,
)

GIB = 1024**3


@pytest.fixture()
def instance() -> MagicMock:
    """
    Return a mock RDSMySQLInstance on a healthy, dedicated parameter group.

    Specced against the real classes so that reading an attribute they do not
    have raises instead of quietly returning another mock — an unspecced mock
    happily answers to a stale name after a rename.
    """
    group = MagicMock(spec=RDSParameterGroup)
    group.name = "test-pg"
    group.is_default = False
    group.attached_instance_ids = ["test-instance"]
    group.value_of.return_value = "0"
    group.snapshot.return_value = [
        {"name": name, "value": None, "source": "engine-default"} for name in CAPTURE_PARAMETERS
    ]

    mock = MagicMock(spec=RDSMySQLInstance)
    mock.db_instance_id = "test-instance"
    mock.engine = "mysql"
    mock.engine_version = "8.0.45"
    mock.status = "available"
    mock.free_storage_bytes = 180 * GIB
    mock.slow_log_files = []
    mock.cloudwatch_log_exports = []
    mock.parameter_group = group
    return mock


@pytest.fixture()
def capture(instance: MagicMock, tmp_path) -> SlowLogCapture:
    """Return a SlowLogCapture writing its state file into a temp directory."""
    return SlowLogCapture(instance, state_file=str(tmp_path / "state.json"))


def test_desired_parameters_flip_log_output_to_file(capture: SlowLogCapture) -> None:
    """log_output=FILE is mandatory: TABLE produces no file and mutes log_slow_extra."""
    assert capture.desired_parameters == {
        "log_output": "FILE",
        "slow_query_log": "1",
        "long_query_time": "0",
        "log_slow_extra": "ON",
        "log_slow_admin_statements": "1",
    }


def test_default_state_file_is_named_after_the_instance(instance: MagicMock) -> None:
    """Without an explicit path the state file carries the DB instance identifier."""
    assert SlowLogCapture(instance).state_file == "ih-query-audit-test-instance.state.json"


def test_desired_parameters_honour_options(instance: MagicMock) -> None:
    """Threshold and extra attributes are configurable."""
    capture = SlowLogCapture(instance, long_query_time=0.5, log_slow_extra=False, log_slow_admin_statements=False)
    assert capture.desired_parameters["long_query_time"] == "0.5"
    assert capture.desired_parameters["log_slow_extra"] == "OFF"
    assert capture.desired_parameters["log_slow_admin_statements"] == "0"


def test_preflight_passes(capture: SlowLogCapture) -> None:
    """A healthy instance with headroom passes."""
    capture.preflight(max_log_size=GIB, min_free_storage=20 * GIB)


def test_preflight_rejects_non_mysql(instance: MagicMock, capture: SlowLogCapture) -> None:
    """Postgres has a different slow-log mechanism entirely."""
    instance.engine = "postgres"
    with pytest.raises(SlowLogCaptureError) as exc_info:
        capture.preflight()
    assert "supports RDS for MySQL" in str(exc_info.value)


def test_preflight_rejects_unavailable_instance(instance: MagicMock, capture: SlowLogCapture) -> None:
    """An instance mid-modification will not apply parameters predictably."""
    instance.status = "modifying"
    with pytest.raises(SlowLogCaptureError) as exc_info:
        capture.preflight()
    assert "expected available" in str(exc_info.value)


def test_preflight_rejects_default_parameter_group(instance: MagicMock, capture: SlowLogCapture) -> None:
    """Default groups cannot be modified, and swapping groups needs a reboot."""
    instance.parameter_group.is_default = True
    instance.parameter_group.name = "default.mysql8.0"
    with pytest.raises(SlowLogCaptureError) as exc_info:
        capture.preflight()
    assert "default parameter group" in str(exc_info.value)


def test_preflight_rejects_shared_parameter_group(instance: MagicMock, capture: SlowLogCapture) -> None:
    """A shared group would turn the slow log up on every attached instance."""
    instance.parameter_group.attached_instance_ids = ["test-instance", "test-instance-replica"]
    with pytest.raises(SlowLogCaptureError) as exc_info:
        capture.preflight()
    assert "attached to 2 instances" in str(exc_info.value)


def test_preflight_allows_shared_group_when_asked(instance: MagicMock, tmp_path) -> None:
    """The shared-group guard is a guard, not a wall."""
    instance.parameter_group.attached_instance_ids = ["test-instance", "test-instance-replica"]
    capture = SlowLogCapture(instance, state_file=str(tmp_path / "state.json"), allow_shared_parameter_group=True)
    capture.preflight()


def test_preflight_rejects_insufficient_storage(instance: MagicMock, capture: SlowLogCapture) -> None:
    """A capture must not be able to fill the data volume."""
    instance.free_storage_bytes = 21 * GIB
    with pytest.raises(SlowLogCaptureError) as exc_info:
        capture.preflight(max_log_size=5 * GIB, min_free_storage=20 * GIB)
    assert "headroom" in str(exc_info.value)


def test_preflight_rejects_unknown_storage(instance: MagicMock, capture: SlowLogCapture) -> None:
    """Unverifiable free space is treated as unsafe, not as fine."""
    instance.free_storage_bytes = None
    with pytest.raises(SlowLogCaptureError) as exc_info:
        capture.preflight(min_free_storage=20 * GIB)
    assert "cannot be verified" in str(exc_info.value)


def test_preflight_propagates_parameter_errors(instance: MagicMock, capture: SlowLogCapture) -> None:
    """A parameter missing from the engine family fails before anything changes."""
    instance.parameter_group.validate_modifiable.side_effect = RDSParameterError("no such parameter")
    with pytest.raises(RDSParameterError):
        capture.preflight()


def test_start_writes_state_file_before_applying(capture: SlowLogCapture, instance: MagicMock) -> None:
    """The state file must exist before the first parameter is touched."""
    seen = {}

    def record_apply(values):
        seen["state_file_exists"] = osp.exists(capture.state_file)
        seen["values"] = values

    instance.parameter_group.apply.side_effect = record_apply
    capture.start()

    assert seen["state_file_exists"] is True
    assert seen["values"] == capture.desired_parameters
    with open(capture.state_file, encoding="utf8") as descriptor:
        state = json.load(descriptor)
    assert state["instance_id"] == "test-instance"
    assert state["parameter_group"] == "test-pg"
    assert [entry["name"] for entry in state["parameters"]] == CAPTURE_PARAMETERS


def test_context_manager_restores_on_exception(capture: SlowLogCapture, instance: MagicMock) -> None:
    """Parameters go back even when the body blows up."""
    with pytest.raises(ValueError):
        with capture:
            raise ValueError("boom")
    instance.parameter_group.restore.assert_called_once()
    assert not osp.exists(capture.state_file)


def test_context_manager_restores_on_interrupt(capture: SlowLogCapture, instance: MagicMock) -> None:
    """Ctrl+C behaves like the shell script's INT trap."""
    with pytest.raises(KeyboardInterrupt):
        with capture:
            raise KeyboardInterrupt
    instance.parameter_group.restore.assert_called_once()


def test_state_file_survives_failed_restore(capture: SlowLogCapture, instance: MagicMock) -> None:
    """If the restore fails the state file stays, so a human can finish the job."""
    instance.parameter_group.restore.side_effect = SlowLogCaptureError("api is down")
    capture.start()
    with pytest.raises(SlowLogCaptureError):
        capture.stop()
    assert osp.exists(capture.state_file)


def test_state_before_start_is_an_error(capture: SlowLogCapture) -> None:
    """There is nothing to record before anything has been recorded."""
    with pytest.raises(SlowLogCaptureError):
        _ = capture.state


def test_stop_without_start_is_a_noop(capture: SlowLogCapture, instance: MagicMock) -> None:
    """Restoring a capture that never started must not touch the parameter group."""
    capture.stop()
    instance.parameter_group.restore.assert_not_called()


def test_captured_bytes_excludes_pre_existing_logs(capture: SlowLogCapture, instance: MagicMock) -> None:
    """Only growth counts — RDS log files predating the capture are not ours."""
    instance.slow_log_files = [{"name": "slowquery/mysql-slowquery.log", "size": 500, "last_written": 1}]
    capture.start()
    instance.slow_log_files = [
        {"name": "slowquery/mysql-slowquery.log", "size": 1500, "last_written": 2},
        {"name": "slowquery/mysql-slowquery.log.2026-08-24.10", "size": 200, "last_written": 3},
    ]
    assert capture.captured_bytes == 1200


def test_watch_stops_on_log_size(capture: SlowLogCapture, instance: MagicMock) -> None:
    """The size limit ends the capture."""
    capture.start()
    instance.slow_log_files = [{"name": "slowquery/mysql-slowquery.log", "size": 5000, "last_written": 1}]
    reason = capture.watch(max_run_time=3600, max_log_size=1000, min_free_storage=GIB)
    assert "log size limit" in reason


def test_watch_stops_on_free_storage(capture: SlowLogCapture, instance: MagicMock) -> None:
    """The storage floor ends the capture before the volume fills."""
    capture.start()
    instance.free_storage_bytes = 5 * GIB
    reason = capture.watch(max_run_time=3600, max_log_size=100 * GIB, min_free_storage=20 * GIB)
    assert "free storage dropped" in reason


def test_watch_stops_on_time(capture: SlowLogCapture, instance: MagicMock) -> None:
    """The time limit ends the capture."""
    capture.start()
    reason = capture.watch(max_run_time=0, max_log_size=100 * GIB, min_free_storage=GIB)
    assert "time limit" in reason


def test_watch_before_start_is_an_error(capture: SlowLogCapture) -> None:
    """Watching a capture that never started is a programming error."""
    with pytest.raises(SlowLogCaptureError):
        capture.watch(max_run_time=1, max_log_size=1, min_free_storage=1)


def test_download_skips_untouched_files(capture: SlowLogCapture, instance: MagicMock, tmp_path) -> None:
    """Log files that did not grow during the window are not downloaded."""
    instance.slow_log_files = [{"name": "slowquery/old.log", "size": 100, "last_written": 1}]
    capture.start()
    instance.slow_log_files = [
        {"name": "slowquery/old.log", "size": 100, "last_written": 1},
        {"name": "slowquery/new.log", "size": 42, "last_written": 2},
    ]
    instance.download_log_file.return_value = str(tmp_path / "new.log")

    paths = capture.download(str(tmp_path / "out"))

    assert len(paths) == 1
    instance.download_log_file.assert_called_once_with("slowquery/new.log", str(tmp_path / "out"))


def test_restore_from_state_file(tmp_path) -> None:
    """A capture can be undone with nothing but its state file."""
    state_file = tmp_path / "state.json"
    state_file.write_text(
        json.dumps(
            {
                "instance_id": "test-instance",
                "parameter_group": "test-pg",
                "started_at": "2026-08-24T00:00:00+00:00",
                "parameters": [{"name": "log_output", "value": "TABLE", "source": "system"}],
            }
        )
    )
    with patch("infrahouse_toolkit.aws.rds.slow_log_capture.RDSParameterGroup") as mock_group, patch(
        "infrahouse_toolkit.aws.rds.slow_log_capture.RDSMySQLInstance"
    ) as mock_instance:
        assert SlowLogCapture.restore_from_state_file(str(state_file), MagicMock()) == "test-instance"

    mock_group.return_value.restore.assert_called_once()
    mock_instance.return_value.wait_parameters_in_sync.assert_called_once()
    assert not state_file.exists()


def test_restore_from_malformed_state_file(tmp_path) -> None:
    """A truncated state file fails loudly instead of half-restoring."""
    state_file = tmp_path / "state.json"
    state_file.write_text('{"instance_id": "test-instance"}')
    with pytest.raises(SlowLogCaptureError) as exc_info:
        SlowLogCapture.restore_from_state_file(str(state_file), MagicMock())
    assert "missing key" in str(exc_info.value)


def test_restore_from_invalid_json(tmp_path) -> None:
    """Garbage in the state file is reported as such."""
    state_file = tmp_path / "state.json"
    state_file.write_text("not json at all")
    with pytest.raises(SlowLogCaptureError) as exc_info:
        SlowLogCapture.restore_from_state_file(str(state_file), MagicMock())
    assert "not valid JSON" in str(exc_info.value)


def test_preflight_warns_about_dormant_cloudwatch_export(instance: MagicMock, capture: SlowLogCapture, caplog) -> None:
    """Flipping log_output=FILE wakes a slowquery export that has been shipping nothing."""
    instance.cloudwatch_log_exports = ["error", "general", "slowquery"]
    instance.parameter_group.value_of.return_value = "TABLE"
    capture.preflight()
    assert "CloudWatch Logs ingestion is billable" in caplog.text


def test_preflight_quiet_when_export_already_live(instance: MagicMock, capture: SlowLogCapture, caplog) -> None:
    """Nothing changes for an instance already writing the log to a file."""
    instance.cloudwatch_log_exports = ["error", "slowquery"]
    instance.parameter_group.value_of.return_value = "FILE"
    capture.preflight()
    assert "billable" not in caplog.text


def test_preflight_quiet_without_export(instance: MagicMock, capture: SlowLogCapture, caplog) -> None:
    """No export configured, nothing to warn about."""
    instance.cloudwatch_log_exports = ["error"]
    instance.parameter_group.value_of.return_value = "TABLE"
    capture.preflight()
    assert "billable" not in caplog.text


def test_start_rolls_back_when_apply_cannot_be_confirmed(capture: SlowLogCapture, instance: MagicMock) -> None:
    """__exit__ never runs if __enter__ raises, so start() must undo itself."""
    instance.wait_parameters_in_sync.side_effect = [RDSError("timed out"), None]
    with pytest.raises(RDSError):
        capture.start()
    instance.parameter_group.restore.assert_called_once()
    assert not osp.exists(capture.state_file)


def test_start_rollback_keeps_state_file_when_it_also_fails(capture: SlowLogCapture, instance: MagicMock) -> None:
    """A failed rollback leaves the breadcrumb behind."""
    instance.wait_parameters_in_sync.side_effect = RDSError("timed out")
    instance.parameter_group.restore.side_effect = RDSError("api is down")
    with pytest.raises(RDSError):
        capture.start()
    assert osp.exists(capture.state_file)
