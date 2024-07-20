"""Terraform S3 backend"""

from os import environ

from infrahouse_toolkit.terraform.backends.tfbackend import TFBackend


class TFS3Backend(TFBackend):
    """
    :py:class:`TFS3Backend` describes a Terraform state stored in AWS S3.

    :param bucket: AWS S3 bucket that stores the state.
    :type bucket: str
    :param key: Path inside the S3 bucket to a file with the state.
        Something like ``path/to/github-control.state``.
    :type key: str
    """

    def __init__(self, bucket: str, key: str, region: str = None):
        self._bucket = bucket
        self._key = key
        self._region = region

    @property
    def bucket(self):
        """S3 bucket name"""
        return self._bucket

    @property
    def id(self):
        """A backend URL that identifies the state file."""
        return str(self)

    @property
    def key(self):
        """Path to the Terraform state in the S3 bucket."""
        return self._key

    @property
    def region(self):
        """AWS region. Taken from the environment variable ``AWS_DEFAULT_REGION`` if one is defined."""
        try:
            return self._region or environ.get("AWS_DEFAULT_REGION")
        except KeyError:
            return None

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return f"s3://{self._bucket}/{self._key}"

    def __eq__(self, other):
        return all((self.bucket == other.bucket, self.key == other.key))
