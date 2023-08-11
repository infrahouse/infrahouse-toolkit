from infrahouse_toolkit.terraform.backends import TFS3Backend
from infrahouse_toolkit.terraform.status import RunOutput, RunResult, TFStatus


def test_comment():
    status = TFStatus(
        TFS3Backend("foo_backet", "path/to/tf.state"), True, RunResult(1, 1, 1), RunOutput("no stdout", None)
    )
    assert isinstance(status.comment, str)
    print(status.comment)


def test_comment_none():
    status = TFStatus(
        TFS3Backend("foo_backet", "path/to/tf.state"),
        True,
        RunResult(None, None, None),
        RunOutput("no stdout", "no stderr"),
        affected_resources=RunResult(None, None, None),
    )
    assert isinstance(status.comment, str)
    print(status.comment)
