"""Tests for :func:`infrahouse_toolkit.aws.resource_discovery.resource_for_arn`."""

import pytest
from infrahouse_core.aws import (
    ASG,
    ACMCertificate,
    CloudFrontCachePolicy,
    CloudFrontDistribution,
    CloudFrontFunction,
    CloudFrontResponseHeadersPolicy,
    CloudWatchLogGroup,
    DynamoDBTable,
    EC2Instance,
    ELBLoadBalancer,
    ELBTargetGroup,
    EventBridgeRule,
    IAMInstanceProfile,
    IAMPolicy,
    IAMRole,
    LambdaFunction,
    NATGateway,
    S3Bucket,
    Secret,
    SecurityGroup,
    SNSTopic,
    SQSQueue,
    Zone,
)

from infrahouse_toolkit.aws.resource_discovery import (
    EBSVolume,
    ECSCapacityProvider,
    ECSCluster,
    ECSService,
    ECSTaskDefinition,
    KeyPair,
    LaunchTemplate,
    NetworkInterface,
    SecurityGroupRule,
    resource_for_arn,
)


@pytest.mark.parametrize(
    "arn, expected_class",
    [
        ("arn:aws:ec2:us-east-1:123456789012:instance/i-0abcdef1234567890", EC2Instance),
        ("arn:aws:ec2:us-east-1:123456789012:security-group/sg-0abcdef1234567890", SecurityGroup),
        ("arn:aws:ec2:us-east-1:123456789012:natgateway/nat-0abcdef1234567890", NATGateway),
        ("arn:aws:ec2:us-east-1:123456789012:network-interface/eni-0abcdef1234567890", NetworkInterface),
        ("arn:aws:ec2:us-east-1:123456789012:security-group-rule/sgr-0abcdef1234567890", SecurityGroupRule),
        ("arn:aws:ec2:us-east-1:123456789012:volume/vol-0abcdef1234567890", EBSVolume),
        ("arn:aws:ec2:us-east-1:123456789012:key-pair/key-0abcdef1234567890", KeyPair),
        ("arn:aws:ec2:us-east-1:123456789012:launch-template/lt-0abcdef1234567890", LaunchTemplate),
        ("arn:aws:iam::123456789012:role/my-role", IAMRole),
        ("arn:aws:iam::123456789012:policy/my-policy", IAMPolicy),
        ("arn:aws:iam::123456789012:instance-profile/my-profile", IAMInstanceProfile),
        ("arn:aws:s3:::my-bucket", S3Bucket),
        (
            "arn:aws:elasticloadbalancing:us-west-2:123456789012:loadbalancer/app/my-lb/50dc6c495c0c9188",
            ELBLoadBalancer,
        ),
        (
            "arn:aws:elasticloadbalancing:us-west-2:123456789012:targetgroup/my-tg/50dc6c495c0c9188",
            ELBTargetGroup,
        ),
        ("arn:aws:lambda:us-east-1:123456789012:function:my-func", LambdaFunction),
        ("arn:aws:dynamodb:us-east-1:123456789012:table/my-table", DynamoDBTable),
        ("arn:aws:secretsmanager:us-east-1:123456789012:secret:my-secret-AbCdEf", Secret),
        ("arn:aws:logs:us-east-1:123456789012:log-group:/aws/lambda/my-func", CloudWatchLogGroup),
        ("arn:aws:events:us-east-1:123456789012:rule/my-rule", EventBridgeRule),
        ("arn:aws:sns:us-west-2:123456789012:my-topic", SNSTopic),
        ("arn:aws:sqs:us-west-2:123456789012:my-queue", SQSQueue),
        (
            "arn:aws:autoscaling:us-west-2:123456789012:autoScalingGroup:guid:autoScalingGroupName/my-asg",
            ASG,
        ),
        ("arn:aws:route53:::hostedzone/Z0123456789ABCDEFGHIJ", Zone),
        ("arn:aws:cloudfront::303467602807:distribution/EN7PRFXV5SHV9", CloudFrontDistribution),
        ("arn:aws:cloudfront::123456789012:cache-policy/658327ea-f89d-4fab-a63d-7e88639e58f6", CloudFrontCachePolicy),
        ("arn:aws:cloudfront::123456789012:function/my-cf-function", CloudFrontFunction),
        (
            "arn:aws:cloudfront::123456789012:response-headers-policy/658327ea-f89d-4fab-a63d-7e88639e58f6",
            CloudFrontResponseHeadersPolicy,
        ),
        (
            "arn:aws:acm:us-east-1:123456789012:certificate/12345678-1234-1234-1234-123456789012",
            ACMCertificate,
        ),
        (
            "arn:aws:ecs:us-west-2:303467602807:task-definition/test-terraform-aws-ecs-cw-agent-daemon:8",
            ECSTaskDefinition,
        ),
        (
            "arn:aws:ecs:us-east-1:303467602807:service/my-cluster/my-service",
            ECSService,
        ),
        (
            "arn:aws:ecs:us-east-1:303467602807:cluster/my-cluster",
            ECSCluster,
        ),
        (
            "arn:aws:ecs:us-east-1:303467602807:capacity-provider/my-cp",
            ECSCapacityProvider,
        ),
    ],
)
def test_resource_for_arn_returns_correct_class(arn: str, expected_class: type) -> None:
    """Verify that the correct infrahouse-core class is instantiated for each ARN."""
    resource = resource_for_arn(arn)
    assert resource is not None, f"Expected {expected_class.__name__} for {arn}, got None"
    assert isinstance(resource, expected_class), f"Expected {expected_class.__name__}, got {type(resource).__name__}"


@pytest.mark.parametrize(
    "arn",
    [
        "not-an-arn",
        # Unsupported EC2 sub-types
        "arn:aws:ec2:us-east-1:123456789012:vpc/vpc-12345",
        "arn:aws:ec2:us-east-1:123456789012:subnet/subnet-12345",
        # Unsupported service
        "arn:aws:redshift:us-east-1:123456789012:cluster:my-cluster",
    ],
)
def test_resource_for_arn_returns_none_for_unsupported(arn: str) -> None:
    """Unsupported ARNs return None."""
    assert resource_for_arn(arn) is None
