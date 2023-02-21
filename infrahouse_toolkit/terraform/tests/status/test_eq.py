from infrahouse_toolkit.terraform.backends import TFS3Backend
from infrahouse_toolkit.terraform.status import RunOutput, RunResult, TFStatus


def test_eq():
    assert TFStatus(
        TFS3Backend("foo_backet", "path/to/tf.state"), True, RunResult(1, 1, 1), RunOutput("no stdout", None)
    ) == TFStatus(TFS3Backend("foo_backet", "path/to/tf.state"), True, RunResult(1, 1, 1), RunOutput("no stdout", None))


def test_eq_no_affrected_res():
    assert TFStatus(
        TFS3Backend("foo_backet", "path/to/tf.state"),
        True,
        RunResult(1, 1, 1),
        RunOutput("no stdout", None),
        affected_resources=RunResult(None, None, None),
    ) == TFStatus(TFS3Backend("foo_backet", "path/to/tf.state"), True, RunResult(1, 1, 1), RunOutput("no stdout", None))


def test_neq():
    assert TFStatus(
        TFS3Backend("foo_backet", "path/to/tf.state"), True, RunResult(1, 1, 1), RunOutput("no stdout", None)
    ) != TFStatus(TFS3Backend("foo_backet", "path/to/tf.state"), True, RunResult(1, 0, 1), RunOutput("no stdout", None))
