"""Auxiliary functions for command line tools."""

import json

import boto3
import click
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


def get_elastic_password(secret_key="elastic_secret"):
    """
    Try to extract the password for user elastic from AWS secretsmanager.

    If the code runs on an elasticsearch node, there is a secret-id with the password in the custom facts.
    Try to extract that secret and return the password.

    :param secret_key: A key in the puppet facts map facts["elasticsearch"][<secret_key>].
        ``elastic_secret`` or ``kibana_system_secret`` are the only supported values.
    :type secret_key: str
    """
    try:
        with open("/etc/puppetlabs/facter/facts.d/custom.json", encoding=DEFAULT_OPEN_ENCODING) as f_custom_facts:
            custom_facts = json.load(f_custom_facts)
            client = boto3.client("secretsmanager")
            response = client.get_secret_value(SecretId=custom_facts["elasticsearch"][secret_key])
            return response["SecretString"]

    except FileNotFoundError:
        return None


def read_from_file_or_prompt(file_path: str, prompt_text="Enter a secret value and press ENTER") -> str:
    """
    Read a string from a file if it exists. If not, prompt a user to enter the string.
    Return the string value.

    :param file_path: Path to the file.
    :type file_path: str
    :param prompt_text: What text to show a user.
    :type prompt_text: str
    :return: The string value whether it was read from the file or entered by teh user.
    """
    if file_path:
        with open(file_path, encoding=DEFAULT_OPEN_ENCODING) as val_desc:
            return val_desc.read()
    else:
        return click.prompt(prompt_text, hide_input=True)
