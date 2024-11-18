"""
cli module exceptions.
"""

from infrahouse_toolkit.cli.exceptions import IHCLIError


class IHGithubError(IHCLIError):
    """ih-github errors."""


class IHVariableNotFound(IHGithubError):
    """GitHub variable doesn't exist."""
