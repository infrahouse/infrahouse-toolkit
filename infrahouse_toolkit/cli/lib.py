"""Auxiliary functions for command line tools."""
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
