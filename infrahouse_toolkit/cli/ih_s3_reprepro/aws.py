"""
.. topic:: ``aws.py``

    AWS helper functions.
"""

from logging import getLogger
from os import environ

import boto3
import requests
from botocore.exceptions import ClientError

LOG = getLogger()
VALUE_MAP = {
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


def assume_role(role_arn, region=None) -> dict:
    """
    Assume a given role and return a dictionary with credentials.

    :param role_arn: Role to be assumed.
    :type role_arn: str
    :param region: AWS region name.
    :type region: str
    :return: A dictionary with three keys: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and
    """
    try:
        LOG.debug("Assuming role %s", role_arn)
        client = boto3.client("sts", region_name=region)
        response = client.assume_role(RoleArn=role_arn, RoleSessionName="ih-s3-reprepro-s3fs")
        LOG.debug("Got credentials %r", response["Credentials"])
        return {var: response["Credentials"].get(key) for var, key in VALUE_MAP.items()}
    except ClientError as err:
        LOG.error(err)
        LOG.debug("To revert environment:\n%s", "\n".join([f"unset {key}" for key in VALUE_MAP]))
        raise


def get_client(service_name, role_arn=None, region=None, session_name=__name__):
    """
    Get an AWS service client assuming a role if specified.

    :param service_name: AWS service. ec2, sts, etc.
    :type service_name: str
    :param role_arn: Role ARN if it needs to be assumed.
    :type role_arn: str
    :param session_name: A human-readable string that tells something about this session.
        Exact value isn't important.
    :type session_name: str
    :param region: AWS region name.
    :type region: str
    :return: AWS boto3 client.
    """
    if role_arn:
        sts = boto3.client("sts", region_name=region)
        aws_iam_role = sts.assume_role(RoleArn=role_arn, RoleSessionName=session_name)
        session = boto3.Session(
            aws_access_key_id=aws_iam_role["Credentials"]["AccessKeyId"],
            aws_secret_access_key=aws_iam_role["Credentials"]["SecretAccessKey"],
            aws_session_token=aws_iam_role["Credentials"]["SessionToken"],
            region_name=region,
        )
        sts = session.client("sts", region_name=region)
        response = sts.get_caller_identity()
        LOG.debug("Assumed role: %s", response)
        return session.client(service_name, region_name=region)

    return boto3.client(service_name, region_name=region)


def get_credentials_from_profile() -> dict:
    """
    Another way to get AWS credentials is from EC2 instance metadata.

    :return: A dictionary with AWS_* variables.
    """
    url = "http://169.254.169.254/latest/meta-data/iam/security-credentials/"
    profile_name = requests.get(url, timeout=10).text
    LOG.debug("Profile name %s", profile_name)
    profile_data = requests.get(f"{url}/{profile_name}", timeout=10).json()
    profile_data["SessionToken"] = profile_data["Token"]

    return {var: profile_data.get(key) for var, key in VALUE_MAP.items()}


def get_credentials_from_environ():
    """Yet another way to get credentials.

    If environment is already configured for AWS access, simply get the credential from the environment.
    This is a situation when a user configures AWS_* in their env.
    Or when a role has been assumed and AWS_* are configured.

    :return: A dictionary with AWS_* variables.
    """
    return {
        "AWS_ACCESS_KEY_ID": environ.get("AWS_ACCESS_KEY_ID"),
        "AWS_SECRET_ACCESS_KEY": environ.get("AWS_SECRET_ACCESS_KEY"),
        "AWS_SESSION_TOKEN": environ.get("AWS_SESSION_TOKEN"),
        "AWSACCESSKEYID": environ.get("AWS_ACCESS_KEY_ID"),
        "AWSSECRETACCESSKEY": environ.get("AWS_SECRET_ACCESS_KEY"),
        "AWSSESSIONTOKEN": environ.get("AWS_SESSION_TOKEN"),
    }
