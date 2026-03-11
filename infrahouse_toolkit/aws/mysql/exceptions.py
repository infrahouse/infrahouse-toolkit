"""MySQL-specific exceptions."""

from infrahouse_toolkit.aws.exceptions import IHAWSException


class MySQLBootstrapError(IHAWSException):
    """Error during MySQL bootstrap process."""


class MySQLInstanceNotFound(IHAWSException):
    """A MySQL instance could not be found in the Auto Scaling group."""
