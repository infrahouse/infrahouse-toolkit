from textwrap import dedent

import pytest

from infrahouse_toolkit.aws import AWSConfig

CONTENT = dedent(
    """
    [default]
    region = us-west-123

    [sso-session foo_session]
    sso_start_url = https://foo.com/start#
    sso_region = us-west-1
    sso_registration_scopes = sso:account:access

    [profile foo_profile]
    sso_session = foo_session
    sso_account_id = 12345678
    sso_role_name = admin
    region = us-west-2

    [sso-session bar_session]
    sso_start_url = https://bar.com/start#
    sso_registration_scopes = sso:account:access

    [profile bar_profile]
    sso_session = bar_session
    sso_account_id = 12345678
    sso_role_name = admin
    region = us-west-2
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
        ("foo_profile", CONTENT, "us-west-1"),
        ("bar_profile", CONTENT, "us-west-123"),
        (None, CONTENT, "us-west-123"),
        ("default", CONTENT, "us-west-123"),
        ("default", CONTENT_2, None),
        ("foo", CONTENT_2, None),
        ("bar", CONTENT_2, None),
        (None, CONTENT_2, None),
    ],
)
def test_sso_region(profile, region, content, tmpdir):
    aws_home = tmpdir.mkdir("home")
    cfg = aws_home.join("config")
    cfg.write(content)
    assert AWSConfig(aws_home=str(aws_home)).get_sso_region(profile) == region
