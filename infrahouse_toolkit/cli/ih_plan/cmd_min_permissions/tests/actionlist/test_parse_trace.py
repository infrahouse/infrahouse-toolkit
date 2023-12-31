from textwrap import dedent

import pytest

from infrahouse_toolkit.cli.ih_plan.cmd_min_permissions import ActionList


@pytest.mark.parametrize(
    "trace, expected_actions",
    [
        (
            '{"aws.operation": "PutScalingPolicy","aws.service": "Auto Scaling"}',
            [
                "autoscaling:PutScalingPolicy",
            ],
        ),
        (
            '{"aws.operation": "DescribePolicies","aws.service": "Auto Scaling"}',
            [
                "autoscaling:DescribePolicies",
            ],
        ),
        (
            '{"rpc.method": "DescribeLogGroups", "rpc.service": "CloudWatch Logs"}',
            [
                "logs:DescribeLogGroups",
            ],
        ),
        (
            '{"rpc.method": "ListTargetsByRule", "rpc.service": "EventBridge"}',
            [
                "events:ListTargetsByRule",
            ],
        ),
        (
            '{"rpc.method": "CompleteMultipartUpload", "rpc.service": "s3"}',
            [
                "kms:CreateGrant",
                "kms:Decrypt",
                "kms:DescribeKey",
                "kms:Encrypt",
                "s3:AbortMultipartUpload",
                "s3:GetObject",
                "s3:ListMultipartUploadParts",
                "s3:PutObject",
                "s3:PutObjectTagging",
            ],
        ),
        (
            '{"rpc.method": "UploadPart", "rpc.service": "s3"}',
            [
                "kms:CreateGrant",
                "kms:Decrypt",
                "kms:DescribeKey",
                "kms:Encrypt",
                "s3:AbortMultipartUpload",
                "s3:GetObject",
                "s3:ListMultipartUploadParts",
                "s3:PutObject",
                "s3:PutObjectTagging",
            ],
        ),
    ],
)
def test_parse_trace(trace, expected_actions, tmpdir):
    tracefile = tmpdir.join("trace")
    tracefile.write(trace)
    actions = ActionList()
    actions.parse_trace(str(tracefile))
    assert actions.actions == expected_actions


@pytest.mark.parametrize(
    "trace_content, expected_permissions",
    [
        (
            dedent(
                """
                {"aws.operation": "HeadBucket","aws.service": "S3"}
                {"rpc.method": "HeadObject", "rpc.service": "S3"}
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
                "s3:GetObject",
            ],
        ),
        (
            dedent(
                """
                {"rpc.method": "CreateBucket", "rpc.service": "S3"}
                {"rpc.method": "CreateTable", "rpc.service": "DynamoDB"}
                """
            ),
            ["s3:CreateBucket", "dynamodb:CreateTable", "s3:PutBucketTagging"],
        ),
        (
            dedent(
                """
                {"aws.operation": "DeletePublicAccessBlock","aws.service": "S3"}
                {"aws.operation": "GetPublicAccessBlock","aws.service": "S3"}
                {"aws.operation": "PutPublicAccessBlock","aws.service": "S3"}
                """
            ),
            ["s3:PutBucketPublicAccessBlock", "s3:GetBucketPublicAccessBlock"],
        ),
        (
            dedent(
                """
                {"tf_resource_type": "aws_s3_bucket_versioning","tf_rpc": "ApplyResourceChange"}
                {"tf_resource_type": "aws_s3_bucket_server_side_encryption_configuration","tf_rpc": "ApplyResourceChange"}
                some garbage
                """
            ),
            ["s3:PutBucketVersioning", "s3:PutEncryptionConfiguration"],
        ),
        (
            dedent(
                """
                {"tf_resource_type": "aws_s3_bucket_versioning","tf_rpc": "ApplyResourceChange"}
                {"tf_resource_type": "aws_s3_bucket_versioning","tf_rpc": "ApplyResourceChange"}
                some garbage
                """
            ),
            ["s3:PutBucketVersioning"],
        ),
    ],
)
def test_parse_trace_permissions_map(tmpdir, trace_content, expected_permissions):
    tracefile = tmpdir.join("trace")
    tracefile.write(trace_content)
    actions = ActionList()
    actions.parse_trace(str(tracefile))
    assert sorted(actions.actions) == sorted(expected_permissions)
