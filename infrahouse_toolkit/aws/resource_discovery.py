"""
AWS resource discovery via the Resource Groups Tagging API.

Uses `infrahouse-core <https://pypi.org/project/infrahouse-core/>`_ resource
classes for existence checks (``resource.exists``) and deletion
(``resource.delete()``).  This module is thin orchestration — service-specific
logic lives in infrahouse-core.
"""

import json
import re
from logging import getLogger
from typing import Dict, List, Optional

import boto3
from botocore.exceptions import ClientError
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
from tabulate import tabulate

LOG = getLogger(__name__)

# ---------------------------------------------------------------------------
# ARN parsing
# ---------------------------------------------------------------------------


def parse_arn(arn: str) -> Optional[Dict[str, Optional[str]]]:
    """
    Parse an ARN into its components.

    ARN format: ``arn:partition:service:region:account-id:resource-type/resource-id``
    or: ``arn:partition:service:region:account-id:resource-type:resource-id``

    :param arn: Amazon Resource Name string.
    :return: Dictionary with keys ``partition``, ``service``, ``region``,
        ``account``, ``resource``, ``resource_type``, and ``resource_id``.
        Returns ``None`` when the ARN cannot be parsed.
    """
    pattern = r"^arn:(?P<partition>[^:]+):(?P<service>[^:]+):(?P<region>[^:]*):(?P<account>[^:]*):(?P<resource>.+)$"
    match = re.match(pattern, arn)
    if not match:
        return None

    result = match.groupdict()

    resource = result["resource"]
    colon_pos = resource.find(":")
    slash_pos = resource.find("/")

    if colon_pos != -1 and (slash_pos == -1 or colon_pos < slash_pos):
        parts = resource.split(":", 1)
        result["resource_type"] = parts[0]
        result["resource_id"] = parts[1]
    elif slash_pos != -1:
        parts = resource.split("/", 1)
        result["resource_type"] = parts[0]
        result["resource_id"] = parts[1]
    else:
        result["resource_type"] = None
        result["resource_id"] = resource

    return result


# ---------------------------------------------------------------------------
# Lightweight resource wrappers (too simple for infrahouse-core)
# ---------------------------------------------------------------------------


class ECSTaskDefinition:
    """Minimal wrapper for ECS task definitions.

    Deletion is a two-step process: deregister (ACTIVE -> INACTIVE),
    then ``delete_task_definitions`` to permanently remove.  No
    dependency teardown needed, so a full infrahouse-core class would
    be overkill.
    """

    def __init__(self, arn: str, region: str = None, session: boto3.Session = None):
        self._arn = arn
        self._region = region
        self._session = session
        self._client_instance = None

    @property
    def _client(self):
        """Lazy-initialise the ECS client (mirrors infrahouse-core pattern)."""
        if self._client_instance is None:
            self._client_instance = (self._session or boto3).client("ecs", region_name=self._region)
        return self._client_instance

    @property
    def exists(self) -> bool:
        """Return ``True`` if the task definition is ACTIVE or INACTIVE.

        Both ACTIVE and INACTIVE revisions still exist in AWS and appear
        in the Resource Groups Tagging API.  We must report INACTIVE ones
        as existing — otherwise they become invisible to the delete command.

        Revisions in ``DELETE_IN_PROGRESS`` state are treated as gone
        because the deletion has already been requested.
        """
        try:
            resp = self._client.describe_task_definition(taskDefinition=self._arn)
            return resp["taskDefinition"]["status"] != "DELETE_IN_PROGRESS"
        except ClientError:
            return False

    def delete(self) -> None:
        """Deregister and then permanently delete the task definition.

        AWS requires deregistration (ACTIVE -> INACTIVE) before a task
        definition can be deleted.  Already-INACTIVE revisions skip
        straight to deletion.
        """
        try:
            self._client.deregister_task_definition(taskDefinition=self._arn)
        except ClientError:
            pass  # Already INACTIVE — proceed to delete.
        self._client.delete_task_definitions(taskDefinitions=[self._arn])


# ---------------------------------------------------------------------------
# ARN → infrahouse-core resource class mapping
# ---------------------------------------------------------------------------


def resource_for_arn(
    arn: str, region: str = None, role_arn: str = None, session: boto3.Session = None
):  # pylint: disable=too-many-return-statements,too-many-branches
    """
    Instantiate an ``infrahouse-core`` resource class for the given ARN.

    :param arn: Amazon Resource Name.
    :param region: AWS region override (uses the ARN region when ``None``).
    :param role_arn: IAM role ARN for cross-account access.
    :param session: Authenticated boto3 session.  When provided the resource
        class uses this session for all API calls (e.g. inheriting
        ``--aws-profile`` credentials).
    :return: An infrahouse-core resource instance with ``exists`` / ``delete()``
        interface, or ``None`` when no matching class is available.
    """
    parsed = parse_arn(arn)
    if not parsed:
        return None

    service = parsed["service"]
    resource_type = parsed["resource_type"]
    resource_id = parsed["resource_id"]
    arn_region = region or parsed["region"] or None
    account = parsed["account"]

    # EC2 resources
    if service == "ec2":
        if resource_type == "instance":
            return EC2Instance(instance_id=resource_id, region=arn_region, role_arn=role_arn, session=session)
        if resource_type == "security-group":
            return SecurityGroup(resource_id, region=arn_region, role_arn=role_arn, session=session)
        if resource_type == "natgateway":
            return NATGateway(resource_id, region=arn_region, role_arn=role_arn, session=session)
        return None

    # IAM (global — no region)
    if service == "iam":
        if resource_type == "role":
            return IAMRole(resource_id, role_arn=role_arn, session=session)
        if resource_type == "policy":
            return IAMPolicy(arn, role_arn=role_arn, session=session)
        if resource_type == "instance-profile":
            return IAMInstanceProfile(resource_id, role_arn=role_arn, session=session)
        return None

    # S3 (global — no region in ARN)
    if service == "s3":
        return S3Bucket(resource_id, role_arn=role_arn, session=session)

    # ELB (ARN-identified)
    if service == "elasticloadbalancing":
        if resource_type == "loadbalancer":
            return ELBLoadBalancer(arn, region=arn_region, role_arn=role_arn, session=session)
        if resource_type == "targetgroup":
            return ELBTargetGroup(arn, region=arn_region, role_arn=role_arn, session=session)
        return None

    # Lambda
    if service == "lambda" and resource_type == "function":
        return LambdaFunction(resource_id, region=arn_region, role_arn=role_arn, session=session)

    # DynamoDB
    if service == "dynamodb" and resource_type == "table":
        return DynamoDBTable(resource_id, region=arn_region, role_arn=role_arn, session=session)

    # Secrets Manager
    if service == "secretsmanager" and resource_type == "secret":
        return Secret(arn, region=arn_region, role_arn=role_arn, session=session)

    # CloudWatch Logs
    if service == "logs" and resource_type == "log-group":
        return CloudWatchLogGroup(resource_id, region=arn_region, role_arn=role_arn, session=session)

    # EventBridge
    if service == "events" and resource_type == "rule":
        return EventBridgeRule(resource_id, region=arn_region, role_arn=role_arn, session=session)

    # SNS (ARN-identified)
    if service == "sns":
        return SNSTopic(arn, region=arn_region, role_arn=role_arn, session=session)

    # SQS (URL-identified — derive from ARN)
    if service == "sqs":
        queue_url = f"https://sqs.{arn_region}.amazonaws.com/{account}/{resource_id}"
        return SQSQueue(queue_url, region=arn_region, role_arn=role_arn, session=session)

    # Auto Scaling
    if service == "autoscaling" and resource_type == "autoScalingGroup":
        return ASG(resource_id, region=arn_region, role_arn=role_arn, session=session)

    # CloudFront (global — no region in ARN)
    if service == "cloudfront":
        if resource_type == "distribution":
            return CloudFrontDistribution(resource_id, role_arn=role_arn, session=session)
        if resource_type == "cache-policy":
            return CloudFrontCachePolicy(resource_id, role_arn=role_arn, session=session)
        if resource_type == "function":
            return CloudFrontFunction(resource_id, role_arn=role_arn, session=session)
        if resource_type == "response-headers-policy":
            return CloudFrontResponseHeadersPolicy(resource_id, role_arn=role_arn, session=session)
        return None

    # ACM
    if service == "acm" and resource_type == "certificate":
        return ACMCertificate(arn, region=arn_region, role_arn=role_arn, session=session)

    # Route 53 (global)
    if service == "route53" and resource_type == "hostedzone":
        return Zone(zone_id=resource_id, role_arn=role_arn, session=session)

    # ECS task definitions (lightweight — handled locally)
    if service == "ecs" and resource_type == "task-definition":
        return ECSTaskDefinition(arn, region=arn_region, session=session)

    return None


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def find_iam_roles_by_tag(session: boto3.Session, tag_key: str, tag_value: Optional[str] = None) -> List[Dict]:
    """
    Find IAM roles matching a tag using the direct IAM API.

    The Resource Groups Tagging API sometimes misses IAM roles, so this
    function provides a fallback by enumerating all roles and checking
    their tags.

    :param session: Authenticated boto3 session.
    :param tag_key: Tag key to search for.
    :param tag_value: Tag value to match.  When ``None``, matches any
        role that has *tag_key* regardless of value.
    :return: List of dicts with ``arn``, ``tags``, and ``exists`` keys.
    """
    client = session.client("iam")
    roles: List[Dict] = []

    for page in client.get_paginator("list_roles").paginate():
        for role in page.get("Roles", []):
            try:
                tag_response = client.list_role_tags(RoleName=role["RoleName"])
                role_tags = {t["Key"]: t["Value"] for t in tag_response.get("Tags", [])}
                if tag_value is None:
                    match = tag_key in role_tags
                else:
                    match = role_tags.get(tag_key) == tag_value
                if match:
                    roles.append({"arn": role["Arn"], "tags": role_tags, "exists": True})
            except ClientError:
                continue
    return roles


def _check_exists(arn: str, region: str = None, session: boto3.Session = None) -> bool:
    """
    Check whether a resource still exists using its infrahouse-core class.

    Falls back to ``True`` (assume exists) when no class is available
    for the given ARN.

    :param arn: Amazon Resource Name.
    :param region: AWS region override.
    :param session: Authenticated boto3 session (forwarded to
        :func:`resource_for_arn`).
    :return: ``True`` if the resource exists or cannot be verified.
    """
    resource = resource_for_arn(arn, region=region, session=session)
    if resource is None:
        LOG.debug("No resource class for %s — assuming it exists", arn)
        return True
    try:
        return resource.exists
    except ClientError as exc:
        LOG.debug("Error checking existence of %s: %s", arn, exc)
        return True


def _tag_filter_matches(tags: Dict[str, str], tag_filter: Dict) -> bool:
    """Check whether a resource's tags satisfy a single filter.

    :param tags: Resource tag dict (``{key: value, ...}``).
    :param tag_filter: Filter dict with ``"key"`` and optional ``"value"``.
    :return: ``True`` when the filter matches.
    """
    key = tag_filter["key"]
    if "value" in tag_filter:
        return tags.get(key) == tag_filter["value"]
    return key in tags


def find_resources_by_tags(  # pylint: disable=too-many-locals
    session: boto3.Session,
    tag_filters: List[Dict],
    verify: bool = True,
) -> List[Dict]:
    """
    Find all resources matching one or more tag key/value pairs.

    Uses the Resource Groups Tagging API with supplemental direct IAM
    enumeration.  When multiple tag filters are provided they are
    combined with AND logic.

    Each filter dict must contain ``"key"`` and may contain ``"value"``.
    When ``"value"`` is omitted the filter matches any resource that
    carries the tag key, regardless of value.

    :param session: Authenticated boto3 session.
    :param tag_filters: List of ``{"key": "<key>"}`` or
        ``{"key": "<key>", "value": "<value>"}`` dicts.
    :param verify: When ``True``, verify each resource still exists via
        the infrahouse-core ``resource.exists`` property.
    :return: List of dicts with ``arn``, ``tags``, and ``exists`` keys.
    """
    client = session.client("resourcegroupstaggingapi")
    resources: List[Dict] = []
    seen_arns: set = set()
    region = session.region_name

    # IAM roles are often missed by the Tagging API — search directly.
    if tag_filters:
        first = tag_filters[0]
        LOG.info("Searching IAM roles directly for %s=%s ...", first["key"], first.get("value", "*"))
        iam_roles = find_iam_roles_by_tag(session, first["key"], first.get("value"))
        for role in iam_roles:
            if all(_tag_filter_matches(role["tags"], tf) for tf in tag_filters):
                resources.append(role)
                seen_arns.add(role["arn"])

    api_tag_filters = []
    for tag_filter in tag_filters:
        api_filter = {"Key": tag_filter["key"]}
        if "value" in tag_filter:
            api_filter["Values"] = [tag_filter["value"]]
        api_tag_filters.append(api_filter)

    LOG.info("Searching via Resource Groups Tagging API ...")
    for page in client.get_paginator("get_resources").paginate(TagFilters=api_tag_filters):
        for mapping in page.get("ResourceTagMappingList", []):
            arn = mapping["ResourceARN"]
            if arn in seen_arns:
                continue
            exists = _check_exists(arn, region=region, session=session) if verify else True
            resources.append(
                {
                    "arn": arn,
                    "tags": {tag["Key"]: tag["Value"] for tag in mapping.get("Tags", [])},
                    "exists": exists,
                }
            )
            seen_arns.add(arn)

    return resources


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def _parse_service_and_type(arn: str) -> str:
    """
    Extract a short ``service/type`` label from an ARN.

    :param arn: Amazon Resource Name.
    :return: Human-readable service/type string (e.g. ``ec2/instance``).
    """
    parsed = parse_arn(arn)
    if not parsed:
        return "unknown"
    service = parsed["service"]
    resource_type = parsed["resource_type"]
    if resource_type:
        return f"{service}/{resource_type}"
    return service


def format_resources_table(resources: List[Dict], show_deleted: bool = False, show_tags: bool = True) -> str:
    """
    Format discovered resources as a ``tabulate`` grid table.

    When *show_tags* is ``True`` the output includes a Tags column with
    JSON-formatted tag key/value pairs, similar to ``ih-ec2 list --tags``.

    :param resources: List of resource dicts from :func:`find_resources_by_tags`.
    :param show_deleted: Include stale/deleted resources in the output.
    :param show_tags: Include a Tags column in the table.
    :return: Formatted string ready for printing.
    """
    selected = resources if show_deleted else [r for r in resources if r["exists"]]
    if not selected:
        return "No resources found."

    rows: List[list] = []
    headers = ["Service/Type", "ARN"]
    if show_tags:
        headers.append("Tags")

    for resource in sorted(selected, key=lambda r: r["arn"]):
        row = [
            _parse_service_and_type(resource["arn"]),
            resource["arn"],
        ]
        if show_tags:
            row.append(
                json.dumps(dict(sorted(resource["tags"].items())), indent=4),
            )
        rows.append(row)

    return tabulate(
        rows,
        headers=headers,
        tablefmt="grid" if show_tags else "outline",
    )


def format_resources_json(resources: List[Dict], show_deleted: bool = False) -> str:
    """
    Format discovered resources as JSON.

    :param resources: List of resource dicts from :func:`find_resources_by_tags`.
    :param show_deleted: Include stale/deleted resources in the output.
    :return: JSON string.
    """
    if show_deleted:
        return json.dumps(resources, indent=2)
    return json.dumps([r for r in resources if r["exists"]], indent=2)


def format_resources_arns(resources: List[Dict], show_deleted: bool = False) -> str:
    """
    Format discovered resources as bare ARNs, one per line.

    :param resources: List of resource dicts from :func:`find_resources_by_tags`.
    :param show_deleted: Include stale/deleted resources in the output.
    :return: Newline-separated ARN string.
    """
    selected = resources if show_deleted else [r for r in resources if r["exists"]]
    return "\n".join(r["arn"] for r in selected)
