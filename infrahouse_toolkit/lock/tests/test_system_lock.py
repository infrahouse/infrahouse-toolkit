import pytest

from infrahouse_toolkit.lock.exceptions import LockAcquireError
from infrahouse_toolkit.lock.system import SystemLock
from infrahouse_toolkit.timeout import timeout


def test_system_lock(tmpdir):
    lock_file = tmpdir.join("lock")
    with pytest.raises(TimeoutError):
        with timeout(1):
            with SystemLock(str(lock_file)):
                with SystemLock(str(lock_file)):
                    pass


@pytest.mark.timeout(3)
def test_system_lock_non_blocking(tmpdir):
    lock_file = tmpdir.join("lock")
    with pytest.raises(LockAcquireError):
        with SystemLock(str(lock_file)):
            with SystemLock(str(lock_file), blocking=False):
                pass
