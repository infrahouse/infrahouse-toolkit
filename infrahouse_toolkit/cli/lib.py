"""Auxiliary functions for command line tools."""
import boto3
import hcl

from infrahouse_toolkit import DEFAULT_OPEN_ENCODING

DEFAULT_TF_BACKEND_FILE = "terraform.tf"


def get_bucket(tf_file=DEFAULT_TF_BACKEND_FILE) -> str:
    """
    Find bucket name in a Terraform backend configuration.

    :param tf_file: Path to the Terraform backend configuration.
    :type tf_file: str
    :return: Bucket name.
    """
    with open(tf_file, encoding=DEFAULT_OPEN_ENCODING) as f_desc:
        obj = hcl.load(f_desc)
        return obj["terraform"]["backend"]["s3"]["bucket"]


def get_backend_key(tf_file=DEFAULT_TF_BACKEND_FILE) -> str:
    """
    Find terraform state filename in a Terraform backend configuration.

    :param tf_file: Path to the Terraform backend configuration.
    :type tf_file: str
    :return: Path to Terraform state in S3.
    """
    with open(tf_file, encoding=DEFAULT_OPEN_ENCODING) as f_desc:
        obj = hcl.load(f_desc)
        return obj["terraform"]["backend"]["s3"]["key"]


def get_s3_client(role: str = None):
    """
    Get a boto3 S3 client to work with AWS S3.
    If a role is given, assume it.

    :param role: ARN of a role to be assumed
    :return: A boto3 S3 client object
    """
    if role:
        client = boto3.client("sts")
        response = client.assume_role(DurationSeconds=900, RoleArn=role, RoleSessionName="infrahouse-toolkit")
        session = boto3.Session(
            aws_access_key_id=response["Credentials"]["AccessKeyId"],
            aws_secret_access_key=response["Credentials"]["SecretAccessKey"],
            aws_session_token=response["Credentials"]["SessionToken"],
        )
    else:
        session = boto3.Session()

    return session.client("s3")
