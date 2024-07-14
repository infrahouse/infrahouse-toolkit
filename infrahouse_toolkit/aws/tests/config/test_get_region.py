from textwrap import dedent

import pytest

from infrahouse_toolkit.aws import AWSConfig

CONTENT = dedent(
    """
    [default]
    region = us-west-123

    [profile foo]
    region = us-west-345

    [profile bar]
    """
)

CONTENT_2 = dedent(
    """
    [profile foo]
    region = us-west-345

    [profile bar]
    """
)


@pytest.mark.parametrize(
    "profile, content, region",
    [
        ("default", CONTENT, "us-west-123"),
        ("foo", CONTENT, "us-west-345"),
        ("bar", CONTENT, "us-west-123"),
        (None, CONTENT, "us-west-123"),
        ("default", CONTENT_2, None),
        ("foo", CONTENT_2, "us-west-345"),
        ("bar", CONTENT_2, None),
        (None, CONTENT_2, None),
    ],
)
def test_region(profile, region, content, tmpdir):
    aws_home = tmpdir.mkdir("home")
    cfg = aws_home.join("config")
    cfg.write(content)
    assert AWSConfig(aws_home=str(aws_home)).get_region(profile) == region
