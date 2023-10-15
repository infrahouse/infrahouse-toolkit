from textwrap import dedent

import pytest

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


@pytest.mark.parametrize(
    "trace_content, expected_permissions",
    [
        (
            dedent(
                """
                {"aws.operation": "HeadBucket","aws.service": "S3"}
                {"aws.operation": "GetBucketAccelerateConfiguration","aws.service": "S3"}
                {"aws.operation": "GetBucketEncryption","aws.service": "S3"}
                {"aws.operation": "GetBucketCors","aws.service": "S3"}
                {"aws.operation": "GetBucketLifecycleConfiguration","aws.service": "S3"}
                {"aws.operation": "GetBucketReplication","aws.service": "S3"}
                {"aws.operation": "GetObjectLockConfiguration","aws.service": "S3"}
                """
            ),
            [
                "s3:GetAccelerateConfiguration",
                "s3:GetBucketCORS",
                "s3:GetBucketObjectLockConfiguration",
                "s3:GetEncryptionConfiguration",
                "s3:GetLifecycleConfiguration",
                "s3:GetReplicationConfiguration",
                "s3:ListBucket",
            ],
        ),
        (
            dedent(
                """
                {"rpc.method": "CreateBucket", "rpc.service": "S3"}
                {"rpc.method": "CreateTable", "rpc.service": "DynamoDB"}
                """
            ),
            ["s3:CreateBucket", "dynamodb:CreateTable"],
        ),
    ],
)
def test_parse_trace_permissions_map(tmpdir, trace_content, expected_permissions):
    tracefile = tmpdir.join("trace")
    tracefile.write(trace_content)
    actions = ActionList()
    actions.parse_trace(str(tracefile))
    assert sorted(actions.actions) == sorted(expected_permissions)
