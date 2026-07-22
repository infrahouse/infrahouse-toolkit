"""
cli module exceptions.
"""

from infrahouse_toolkit.cli.exceptions import IHCLIError


class IHOpenVPNError(IHCLIError):
    """ih-openvpn errors."""


class GoogleNotConfigured(IHOpenVPNError):
    """
    The Google Workspace side of the integration is not set up yet.

    Raised for conditions an operator is expected to hit *before* finishing
    setup -- delegation not authorized, scope not granted, subject not an admin
    -- and never for failures that appear after a working deployment. The
    command maps it to the ``EX_CONFIG`` (78) exit status.
    """


class EmptyDirectory(IHOpenVPNError):
    """
    A Workspace answered a directory listing with no active users at all.

    A live query that returns nobody is a failed lookup, not the news that every
    employee was deactivated: acting on it would revoke every certificate. Unlike
    :py:class:`GoogleNotConfigured` this is not an expected pre-deployment state,
    so the command maps it to exit status 1.
    """
