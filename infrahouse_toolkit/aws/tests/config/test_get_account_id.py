from textwrap import dedent

import pytest

from infrahouse_toolkit.aws import AWSConfig

CONTENT = dedent(
    """
    [default]
    sso_account_id = 123

    [profile foo]
    sso_account_id = 456
    """
)


@pytest.mark.parametrize(
    "profile, account_id",
    [
        (
            "default",
            "123",
        ),
        (
            "foo",
            "456",
        ),
        (
            None,
            "123",
        ),
    ],
)
def test_account_id(profile, account_id, tmpdir):
    aws_home = tmpdir.mkdir("home")
    cfg = aws_home.join("config")
    cfg.write(CONTENT)
    assert AWSConfig(aws_home=str(aws_home)).get_account_id(profile) == account_id
