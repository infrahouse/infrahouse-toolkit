import pytest

from infrahouse_toolkit.terraform.backends import (
    IHUnknownBackend,
    TFS3Backend,
    get_backend,
)


def test_get_backend_raises():
    with pytest.raises(IHUnknownBackend):
        get_backend("foo")


def test_get_backend():
    assert get_backend("s3://foo-bucket/foo.key") == TFS3Backend("foo-bucket", "foo.key")
