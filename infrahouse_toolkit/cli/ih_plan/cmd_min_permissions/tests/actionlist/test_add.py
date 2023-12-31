import pytest

from infrahouse_toolkit.cli.ih_plan.cmd_min_permissions import ActionList


def test_add_sorted():
    """Ensure sorted order"""
    actions1 = ActionList()
    actions1.add("foo")
    actions1.add("bar")

    actions2 = ActionList()
    actions2.add("bar")
    actions2.add("foo")

    assert actions1.actions == actions2.actions


def test_add():
    """add() an action and maintain uniqueness."""
    actions = ActionList()
    actions.add("foo")
    assert actions.actions == ["foo"]

    actions.add("foo")
    assert actions.actions == ["foo"]

    actions.add("bar")
    assert "bar" in actions.actions
    assert "foo" in actions.actions


@pytest.mark.parametrize(
    "action, dependent_actions",
    [
        (
            "autoscaling:CreateAutoScalingGroup",
            [
                "autoscaling:CreateAutoScalingGroup",
                "iam:PassRole",
                "iam:CreateServiceLinkedRole",
                "ec2:CreateTags",
                "ec2:RunInstances",
            ],
        ),
        (
            "logs:CreateLogGroup",
            [
                "logs:CreateLogGroup",
                "logs:TagResource",
            ],
        ),
        (
            "lambda:CreateFunction",
            [
                "lambda:CreateFunction",
                "lambda:TagResource",
            ],
        ),
        (
            "s3:PutObject",
            [
                "kms:Decrypt",
                "kms:CreateGrant",
                "kms:DescribeKey",
                "kms:Encrypt",
                "s3:PutObject",
                "s3:PutObjectTagging",
                "s3:AbortMultipartUpload",
                "s3:GetObject",
                "s3:ListMultipartUploadParts",
            ],
        ),
        (
            "events:PutRule",
            [
                "events:PutRule",
                "events:TagResource",
            ],
        ),
        (
            "events:PutTargets",
            [
                "events:PutTargets",
                "events:TagResource",
            ],
        ),
        (
            "iam:CreateInstanceProfile",
            [
                "iam:CreateInstanceProfile",
                "iam:TagInstanceProfile",
            ],
        ),
        (
            "iam:CreateInstanceProfile",
            [
                "iam:CreateInstanceProfile",
                "iam:TagInstanceProfile",
            ],
        ),
        (
            "s3:CreateBucket",
            [
                "s3:CreateBucket",
                "s3:PutBucketTagging",
            ],
        ),
    ],
)
def test_add_with_dependency(action, dependent_actions):
    actions = ActionList()
    actions.add(action)

    for dependency in dependent_actions:
        assert dependency in actions.actions


def test_add_with_rewrite():
    actions = ActionList()
    actions.add("auto scaling:foo")

    assert actions.actions == ["autoscaling:foo"]
