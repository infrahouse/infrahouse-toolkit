"""
:py:mod:`infrahouse_toolkit.terraform` exceptions.
"""

from infrahouse_toolkit.exceptions import IHException


class IHTFException(IHException):
    """Terraform related exceptions."""


class IHParseError(IHTFException):
    """Error happening when parsing fails."""
