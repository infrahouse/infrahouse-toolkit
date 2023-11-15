from textwrap import dedent

import pytest

from infrahouse_toolkit.aws.config import AWSConfig


@pytest.mark.parametrize(
    "config_content, profiles",
    [
        ("", []),
        (
            dedent(
                """
                [default]
                """
            ),
            ["default"],
        ),
        (
            dedent(
                """
                [default]
                [profile foo]
                [other section]
                """
            ),
            ["default", "foo"],
        ),
    ],
)
def test_profiles(config_content, profiles, tmpdir):
    aws_home = tmpdir.mkdir("home")
    cfg = aws_home.join("config")
    cfg.write(config_content)
    assert AWSConfig(aws_home=str(aws_home)).profiles == profiles
