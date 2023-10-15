from textwrap import dedent

from click.testing import CliRunner

from infrahouse_toolkit.cli.ih_plan import ih_plan


def test_help():
    runner = CliRunner()
    # noinspection PyTypeChecker
    result = runner.invoke(ih_plan, ["min-permissions", "--help"])
    assert result.exit_code == 0
    assert "Usage: ih-plan min-permissions" in result.output


def test_simple(tmpdir):
    tracefile = tmpdir.join("trace")
    tracefile.write(
        dedent(
            """
            {"aws.operation": "PutScalingPolicy","aws.service": "Auto Scaling"}
            {"aws.operation": "DescribePolicies","aws.service": "Auto Scaling"}
            """
        )
    )

    runner = CliRunner()
    # noinspection PyTypeChecker
    result = runner.invoke(ih_plan, ["min-permissions", str(tracefile)])
    assert result.exit_code == 0
    print(result.output)
    assert (
        result.output
        == """## Existing 0 actions:
[]
## 2 new action(s):
[
    "autoscaling:DescribePolicies",
    "autoscaling:PutScalingPolicy"
]
## Old and new actions together excluding duplicates, 2 in total:
[
    "autoscaling:DescribePolicies",
    "autoscaling:PutScalingPolicy"
]
"""
    )


def test_simple_existing(tmpdir):
    tracefile = tmpdir.join("trace")
    tracefile.write(
        dedent(
            """
                {"tf_resource_type": "aws_s3_bucket_versioning","tf_rpc": "ApplyResourceChange"}
                {"tf_resource_type": "aws_s3_bucket_versioning","tf_rpc": "ApplyResourceChange"}
            """
        )
    )

    existing_actions = tmpdir.join("existing.json")
    existing_actions.write(
        dedent(
            """
            ["s3:PutBucketVersioning"]
            """
        )
    )

    runner = CliRunner()
    # noinspection PyTypeChecker
    result = runner.invoke(ih_plan, ["min-permissions", "--existing-actions", str(existing_actions), str(tracefile)])
    assert result.exit_code == 0
    print(result.output)
    assert (
        result.output
        == """## Existing 1 actions:
[
    "s3:PutBucketVersioning"
]
## 0 new action(s):
[]
## Old and new actions together excluding duplicates, 1 in total:
[
    "s3:PutBucketVersioning"
]
"""
    )
