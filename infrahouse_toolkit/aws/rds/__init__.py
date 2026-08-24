"""
RDS helpers.

Provides :class:`RDSMySQLInstance` and :class:`RDSParameterGroup` for reading and
changing an RDS DB instance's configuration, :class:`SlowLogCapture` for
running a bounded slow query log capture, and :class:`QueryDigest` for turning
the result into a ranked query profile with ``pt-query-digest``.
"""

from infrahouse_toolkit.aws.rds.exceptions import (
    QueryDigestError,
    RDSError,
    RDSInstanceNotFound,
    RDSParameterError,
    SlowLogCaptureError,
)
from infrahouse_toolkit.aws.rds.instance import RDSMySQLInstance
from infrahouse_toolkit.aws.rds.parameter_group import RDSParameterGroup
from infrahouse_toolkit.aws.rds.query_digest import QueryDigest
from infrahouse_toolkit.aws.rds.slow_log_capture import (
    CAPTURE_PARAMETERS,
    SlowLogCapture,
)

__all__ = [
    "CAPTURE_PARAMETERS",
    "QueryDigest",
    "QueryDigestError",
    "RDSError",
    "RDSMySQLInstance",
    "RDSInstanceNotFound",
    "RDSParameterError",
    "RDSParameterGroup",
    "SlowLogCapture",
    "SlowLogCaptureError",
]
