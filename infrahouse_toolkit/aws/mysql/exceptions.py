"""MySQL-specific exceptions."""

from infrahouse_toolkit.aws.exceptions import IHAWSException


class MySQLBootstrapError(IHAWSException):
    """Error during MySQL bootstrap process."""
