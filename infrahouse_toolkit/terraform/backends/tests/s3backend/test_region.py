from os import environ

import pytest

from infrahouse_toolkit.terraform.backends.s3backend import TFS3Backend


@pytest.mark.parametrize(
    "aws_default_region, args, expected",
    [
        (None, ("foobucket", "foo.key"), None),
        ("foo_region", ("foobucket", "foo.key"), "foo_region"),
        ("foo_region", ("foobucket", "foo.key", "bar_region"), "bar_region"),
    ],
)
def test_region(aws_default_region, args, expected):
    if aws_default_region:
        # noinspection PyTypeChecker
        environ["AWS_DEFAULT_REGION"] = aws_default_region
    elif "AWS_DEFAULT_REGION" in environ:
        del environ["AWS_DEFAULT_REGION"]
    assert TFS3Backend(*args).region == expected
