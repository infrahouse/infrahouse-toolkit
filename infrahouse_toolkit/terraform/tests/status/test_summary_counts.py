from infrahouse_toolkit.terraform.backends.s3backend import TFS3Backend
from infrahouse_toolkit.terraform.status import RunOutput, RunResult, TFStatus


def test_summary_counts():
    status = TFStatus(
        TFS3Backend("foo_backet", "path/to/tf.state"),
        True,
        RunResult(1, 1, 1),
        RunOutput("no stdout", "no stderr"),
        affected_resources=RunResult(["a"], ["b"], ["c"]),
    )
    print("")
    print(status.summary_counts)
    status.success = False
    print("")
    print(status.summary_counts)


def test_summary_counts_none():
    status = TFStatus(
        TFS3Backend("foo_backet", "path/to/tf.state"),
        True,
        RunResult(None, None, None),
        RunOutput("no stdout", "no stderr"),
        affected_resources=RunResult(None, None, None),
    )
    assert status.success is True
    print("")
    print(status.summary_counts)
