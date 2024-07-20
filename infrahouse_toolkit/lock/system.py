"""
A system-wide Lock class.
Where the system is a server, computer, container, and/or file system.
"""

from fcntl import LOCK_EX, LOCK_NB, LOCK_UN, flock

from infrahouse_toolkit import DEFAULT_OPEN_ENCODING
from infrahouse_toolkit.lock.base import BaseLock
from infrahouse_toolkit.lock.exceptions import LockAcquireError


class SystemLock(BaseLock):
    """
    Acquire a system-wide lock.

    :param lockfile: Path to a file on the local filesystem.
    :type lockfile: str
    :param blocking: Whether the caller should wait for the lock or exception
        should be raised. If blocking is True, the caller will wait.
    :type blocking: bool
    :raise LockAcquireError: If we tried to acquire the lock in a non-blocking mode
        and the lock is taken by somebody else.
    """

    def __init__(self, lockfile: str, blocking: bool = True):
        self._lockfile = lockfile
        self._blocking = blocking
        self._f_desc = None
        super().__init__()
        self._name = f"{self.__class__.name}@{self._lockfile}"

    def __enter__(self):
        self._f_desc = open(self._lockfile, "a", encoding=DEFAULT_OPEN_ENCODING)
        try:
            flock(self._f_desc, LOCK_EX if self._blocking else LOCK_EX | LOCK_NB)
        except BlockingIOError as exc:
            raise LockAcquireError(f"Failed to get an exclusive lock on {self._lockfile}") from exc

    def __exit__(self, exc_type, exc_val, exc_tb):
        flock(self._f_desc, LOCK_UN)
