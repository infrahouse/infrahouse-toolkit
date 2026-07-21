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
