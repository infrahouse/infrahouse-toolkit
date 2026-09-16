"""Skeema-specific exceptions."""

from infrahouse_toolkit.exceptions import IHException


class SkeemaError(IHException):
    """Generic Skeema error."""


class SkeemaDiffError(SkeemaError):
    """``skeema diff`` failed, so its output does not describe everything a push would do."""


class SkeemaDigestMismatch(SkeemaError):
    """The pending diff is no longer the one that was approved."""
