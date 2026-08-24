"""RDS-specific exceptions."""

from infrahouse_toolkit.aws.exceptions import IHAWSException


class RDSError(IHAWSException):
    """Generic RDS error."""


class RDSInstanceNotFound(RDSError):
    """A DB instance could not be found."""


class RDSParameterError(RDSError):
    """A DB parameter cannot be read or modified as requested."""


class SlowLogCaptureError(RDSError):
    """Error during a slow query log capture."""


class QueryDigestError(RDSError):
    """Error while running ``pt-query-digest``."""
