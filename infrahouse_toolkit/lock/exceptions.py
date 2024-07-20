"""
Lock module exceptions.
"""

from infrahouse_toolkit.exceptions import IHException


class LockAcquireError(IHException):
    """When failed to acquire a lock."""
