"""
.. topic:: ``aws.py``

    AWS helper functions.
"""

import boto3
from botocore.exceptions import ClientError

from infrahouse_toolkit import LOG


def assume_role(role_arn) -> dict:
    """
    Assume a given role and return a dictionary with credentials.

    :param role_arn: Role to be assumed.
    :type role_arn: str
    :return: A dictionary with three keys: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and
    """
    value_map = {
        "AWS_ACCESS_KEY_ID": "AccessKeyId",
        "AWS_SECRET_ACCESS_KEY": "SecretAccessKey",
        "AWS_SESSION_TOKEN": "SessionToken",
        # These are old s3.fs options
        # Soon they will be deprecated
        # https://github.com/s3fs-fuse/s3fs-fuse/pull/1729
        "AWSACCESSKEYID": "AccessKeyId",
        "AWSSECRETACCESSKEY": "SecretAccessKey",
        "AWSSESSIONTOKEN": "SessionToken",
    }
    try:
        LOG.debug("Assuming role %s", role_arn)
        client = boto3.client("sts")
        response = client.assume_role(RoleArn=role_arn, RoleSessionName="ih-s3-reprepro-s3fs")
        LOG.debug("Got credentials %r", response["Credentials"])
        return {var: response["Credentials"].get(key) for var, key in value_map.items()}
    except ClientError as err:
        LOG.error(err)
        LOG.debug("To revert environment:\n%s", "\n".join([f"unset {key}" for key in value_map]))
        raise


def get_client(service_name, role_arn=None, session_name=__name__):
    """
    Get an AWS service client assuming a role if specified.

    :param service_name: AWS service. ec2, sts, etc.
    :type service_name: str
    :param role_arn: Role ARN if it needs to be assumed.
    :type role_arn: str
    :param session_name: A human-readable string that tells something about this session.
        Exact value isn't important.
    :type session_name: str
    :return: AWS boto3 client.
    """
    if role_arn:
        sts = boto3.client("sts")
        aws_iam_role = sts.assume_role(RoleArn=role_arn, RoleSessionName=session_name)
        session = boto3.Session(
            aws_access_key_id=aws_iam_role["Credentials"]["AccessKeyId"],
            aws_secret_access_key=aws_iam_role["Credentials"]["SecretAccessKey"],
            aws_session_token=aws_iam_role["Credentials"]["SessionToken"],
        )
        sts = session.client("sts")
        response = sts.get_caller_identity()
        LOG.debug("Assumed role: %s", response)
        return session.client(service_name)

    return boto3.client(service_name)
