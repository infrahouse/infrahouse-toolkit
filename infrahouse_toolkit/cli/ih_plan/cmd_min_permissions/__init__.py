"""
.. topic:: ``ih-plan min-permissions``

    A ``ih-plan min-permissions`` subcommand.

    See ``ih-plan min-permissions --help`` for more details.
"""

import json
from json import JSONDecodeError

import click

from infrahouse_toolkit import DEFAULT_OPEN_ENCODING


@click.command(name="min-permissions")
@click.option("--existing-actions", help="A file with permissions.", default=None)
@click.argument("trace_file")
def cmd_min_permissions(existing_actions, trace_file):
    """
    Parse Terraform trace file and produce an action list from the trace.

    The trace file contains entries with AWS actions. The command
    finds the actions and AWS services to generate a list that
    you can add to an AWS policy.
    It's useful to prepare the least privileges policy.

    The output looks similar to this:

    \b
    [
        "ec2:DeleteNatGateway",
        "ec2:DescribeAddresses",
        "ec2:DescribeInternetGateways",
        "ec2:DescribeNatGateways",
    ]

    """
    actions = ActionList()
    if existing_actions:
        actions.load_from_file(existing_actions)

    print(f"## Existing {actions.count} actions:")
    print(actions)

    new_actions = ActionList()
    new_actions.parse_trace(trace_file, existing=actions.actions)
    print(f"## {new_actions.count} new action(s):")
    print(str(new_actions))

    combined_actions = ActionList()
    for action in actions.actions + new_actions.actions:
        combined_actions.add(action)

    print(f"## Old and new actions together excluding duplicates, {combined_actions.count} in total:")
    print(str(combined_actions))


class ActionList:
    """
    List of AWS actions. Action here is a string as in AWS's policy e.g. ``ec2:DescribeInstances``.

    """

    SERVICE_NAMING_MAP = {
        "auto scaling": "autoscaling",
        "elastic load balancing v2": "elasticloadbalancing",
        "route 53": "route53",
        "secrets manager": "secretsmanager",
        "cloudwatch logs": "logs",
        "eventbridge": "events",
    }
    PERMISSION_NAMING_MAP = {
        "HeadBucket": "ListBucket",
        "HeadObject": "GetObject",
        "CreateMultipartUpload": "PutObject",
        "UploadPart": "PutObject",
        "CompleteMultipartUpload": "PutObject",
        "GetBucketAccelerateConfiguration": "GetAccelerateConfiguration",
        "GetBucketEncryption": "GetEncryptionConfiguration",
        "GetBucketCors": "GetBucketCORS",
        "GetBucketLifecycleConfiguration": "GetLifecycleConfiguration",
        "GetBucketReplication": "GetReplicationConfiguration",
        "GetObjectLockConfiguration": "GetBucketObjectLockConfiguration",
        "DeletePublicAccessBlock": "PutBucketPublicAccessBlock",
        "GetPublicAccessBlock": "GetBucketPublicAccessBlock",
        "PutPublicAccessBlock": "PutBucketPublicAccessBlock",
    }
    # Some permissions require additional ones.
    REQUIRED_EXTRA_PERMISSIONS_MAP = {
        "autoscaling:CreateAutoScalingGroup": [
            "iam:PassRole",
            "iam:CreateServiceLinkedRole",
            "ec2:CreateTags",
            "ec2:RunInstances",
        ],
        "autoscaling:UpdateAutoScalingGroup": ["iam:PassRole"],
        "elasticloadbalancing:CreateLoadBalancer": ["elasticloadbalancing:AddTags"],
        "iam:AddRoleToInstanceProfile": ["iam:PassRole"],
        "iam:CreateInstanceProfile": ["iam:TagInstanceProfile"],
        "ec2:CreateLaunchTemplate": ["ec2:CreateTags"],
        "ec2:ImportKeyPair": ["ec2:CreateTags"],
        "ec2:RunInstances": ["ec2:CreateTags"],
        "logs:CreateLogGroup": ["logs:TagResource"],
        "lambda:CreateFunction": ["lambda:TagResource"],
        "s3:CreateBucket": ["s3:PutBucketTagging"],
        "s3:PutObject": [
            "kms:Decrypt",
            "kms:CreateGrant",
            "kms:DescribeKey",
            "kms:Encrypt",
            "s3:AbortMultipartUpload",
            "s3:GetObject",
            "s3:ListMultipartUploadParts",
            "s3:PutObjectTagging",
        ],
        "events:PutRule": ["events:TagResource"],
        "events:PutTargets": ["events:TagResource"],
    }

    def __init__(self):
        self._actions = set()

    @property
    def actions(self) -> list:
        """List of action strings."""
        return sorted(list(self._actions))

    @property
    def count(self) -> int:
        """Number of actions in the list."""
        return len(self._actions)

    def add(self, action: str):
        """Add a new action. Convert service name to the AWS policy format and add dependent actions if any."""
        norm_action = self._normalize_action(action)
        self._actions.add(norm_action)
        for dependency in self.REQUIRED_EXTRA_PERMISSIONS_MAP.get(str(norm_action), []):
            self._actions.add(dependency)

    def load_from_file(self, file):
        """Load actions from a file with a JSON. The JSON should be an array of strings."""
        with open(file, encoding=DEFAULT_OPEN_ENCODING) as f_desc:
            for action in json.loads(f_desc.read()):
                self.add(action)

    def parse_trace(self, file, existing=None):
        """Inspect a Terraform trace file and collect actions"""
        existing_permissions = existing or []
        with open(file, encoding=DEFAULT_OPEN_ENCODING) as f_decs:
            for line in f_decs.readlines():
                try:
                    operation = json.loads(line)
                    operation_key = "aws.operation" if "aws.operation" in operation else "rpc.method"
                    service_key = "aws.service" if "aws.service" in operation else "rpc.service"
                    if all((operation_key in operation, service_key in operation)):
                        service_name = operation[service_key].lower()
                        permission = self._normalize_action(f"{service_name}:{operation[operation_key]}")
                        if permission not in existing_permissions:
                            self.add(permission)
                    elif all(
                        (
                            operation.get("tf_resource_type") == "aws_s3_bucket_versioning",
                            operation.get("tf_rpc") == "ApplyResourceChange",
                        )
                    ):
                        permission = "s3:PutBucketVersioning"
                    elif all(
                        (
                            operation.get("tf_resource_type") == "aws_s3_bucket_server_side_encryption_configuration",
                            operation.get("tf_rpc") == "ApplyResourceChange",
                        )
                    ):
                        permission = "s3:PutEncryptionConfiguration"
                    else:
                        continue

                    if permission not in existing_permissions:
                        self.add(permission)

                except JSONDecodeError:
                    pass

    def _normalize_action(self, action):
        if ":" in action:
            s_part, a_part = action.split(":")
            return f"{self.SERVICE_NAMING_MAP.get(s_part, s_part)}:{self.PERMISSION_NAMING_MAP.get(a_part, a_part)}"
        return action

    def __str__(self):
        return json.dumps(self.actions, indent=4)
