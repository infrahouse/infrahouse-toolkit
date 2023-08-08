from time import sleep

import pytest

from infrahouse_toolkit.timeout import timeout


def test_timeout():
    with pytest.raises(TimeoutError):
        with timeout(1):
            sleep(3)
