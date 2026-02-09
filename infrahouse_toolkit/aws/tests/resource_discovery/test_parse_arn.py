"""Tests for :func:`infrahouse_toolkit.aws.resource_discovery.parse_arn`."""

import pytest

from infrahouse_toolkit.aws.resource_discovery import parse_arn


@pytest.mark.parametrize(
    "arn, expected",
    [
        # EC2 instance — slash separator
        (
            "arn:aws:ec2:us-east-1:123456789012:instance/i-0abcdef1234567890",
            {
                "partition": "aws",
                "service": "ec2",
                "region": "us-east-1",
                "account": "123456789012",
                "resource": "instance/i-0abcdef1234567890",
                "resource_type": "instance",
                "resource_id": "i-0abcdef1234567890",
            },
        ),
        # IAM role — slash separator
        (
            "arn:aws:iam::123456789012:role/my-role",
            {
                "partition": "aws",
                "service": "iam",
                "region": "",
                "account": "123456789012",
                "resource": "role/my-role",
                "resource_type": "role",
                "resource_id": "my-role",
            },
        ),
        # SNS topic — no separator (just resource id)
        (
            "arn:aws:sns:us-west-2:123456789012:my-topic",
            {
                "partition": "aws",
                "service": "sns",
                "region": "us-west-2",
                "account": "123456789012",
                "resource": "my-topic",
                "resource_type": None,
                "resource_id": "my-topic",
            },
        ),
        # CloudWatch Logs — colon separator
        (
            "arn:aws:logs:us-east-1:123456789012:log-group:/aws/lambda/my-func",
            {
                "partition": "aws",
                "service": "logs",
                "region": "us-east-1",
                "account": "123456789012",
                "resource": "log-group:/aws/lambda/my-func",
                "resource_type": "log-group",
                "resource_id": "/aws/lambda/my-func",
            },
        ),
        # S3 bucket — empty region
        (
            "arn:aws:s3:::my-bucket",
            {
                "partition": "aws",
                "service": "s3",
                "region": "",
                "account": "",
                "resource": "my-bucket",
                "resource_type": None,
                "resource_id": "my-bucket",
            },
        ),
        # Auto Scaling group — colon separator
        (
            "arn:aws:autoscaling:us-west-2:123456789012:autoScalingGroup:guid:autoScalingGroupName/my-asg",
            {
                "partition": "aws",
                "service": "autoscaling",
                "region": "us-west-2",
                "account": "123456789012",
                "resource": "autoScalingGroup:guid:autoScalingGroupName/my-asg",
                "resource_type": "autoScalingGroup",
                "resource_id": "guid:autoScalingGroupName/my-asg",
            },
        ),
        # ELB — complex path
        (
            "arn:aws:elasticloadbalancing:us-west-2:123456789012:loadbalancer/app/my-lb/50dc6c495c0c9188",
            {
                "partition": "aws",
                "service": "elasticloadbalancing",
                "region": "us-west-2",
                "account": "123456789012",
                "resource": "loadbalancer/app/my-lb/50dc6c495c0c9188",
                "resource_type": "loadbalancer",
                "resource_id": "app/my-lb/50dc6c495c0c9188",
            },
        ),
    ],
)
def test_parse_arn(arn: str, expected: dict) -> None:
    """Verify that parse_arn correctly decomposes standard ARN formats."""
    assert parse_arn(arn) == expected


def test_parse_arn_invalid() -> None:
    """Non-ARN strings return None."""
    assert parse_arn("not-an-arn") is None
    assert parse_arn("") is None
