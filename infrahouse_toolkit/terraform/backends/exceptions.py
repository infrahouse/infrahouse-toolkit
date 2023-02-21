"""
:py:mod:`infrahouse_toolkit.terraform.backend` exceptions.
"""

from infrahouse_toolkit.terraform.exceptions import IHTFException


class IHBackendException(IHTFException):
    """Terraform backend exceptions."""


class IHUnknownBackend(IHBackendException):
    """Not supported Terraform backend."""
