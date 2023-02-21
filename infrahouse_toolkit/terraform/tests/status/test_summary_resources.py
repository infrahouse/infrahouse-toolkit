from os import path as osp

from infrahouse_toolkit.terraform import parse_plan
from infrahouse_toolkit.terraform.backends.s3backend import TFS3Backend
from infrahouse_toolkit.terraform.status import RunOutput, RunResult, TFStatus


def test_summary_resources():
    counts, resources = parse_plan(
        open(osp.join(osp.dirname(osp.realpath(__file__)), "../plans/plan-0-0-0.stdout")).read(),
    )
    status = TFStatus(
        TFS3Backend("foo_backet", "path/to/tf.state"),
        True,
        counts,
        RunOutput("no stdout", "no stderr"),
        affected_resources=resources,
    )
    print("")
    print(status.summary_resources)
