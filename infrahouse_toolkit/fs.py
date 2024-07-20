"""
InfraHouse Toolkit file system module.
"""

from logging import getLogger
from os import chmod, stat

LOG = getLogger(__name__)


def ensure_permissions(path: str, permissions: int):
    """
    For a path on the file system check permissions and set if they differ.

    :param path: Filesystem path to a file or directory.
    :type path: str
    :param permissions: Permissions the file or directory must have. Can be an integer like 0o755 or 0o644.
    :type permissions: int
    """
    result = stat(path)
    set_permissions = result.st_mode & 0o777
    LOG.debug("%s permissions: 0o%o", path, set_permissions)
    if set_permissions != permissions:
        LOG.debug("Setting %s permissions to 0o%o", path, permissions)
        chmod(path, permissions)
