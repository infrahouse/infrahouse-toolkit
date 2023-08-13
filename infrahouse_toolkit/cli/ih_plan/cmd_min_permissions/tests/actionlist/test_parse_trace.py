from textwrap import dedent

from infrahouse_toolkit.cli.ih_plan.cmd_min_permissions import ActionList


def test_parse_trace(tmpdir):
    tracefile = tmpdir.join("trace")
    tracefile.write(
        dedent(
            """
            {"aws.operation": "PutScalingPolicy","aws.service": "Auto Scaling"}
            {"aws.operation": "DescribePolicies","aws.service": "Auto Scaling"}
            """
        )
    )
    actions = ActionList()
    actions.parse_trace(str(tracefile))
    assert actions.actions == [
        "autoscaling:DescribePolicies",
        "autoscaling:PutScalingPolicy",
    ]
