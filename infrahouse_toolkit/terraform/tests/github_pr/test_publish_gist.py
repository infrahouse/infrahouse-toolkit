from os import environ

import pytest
from github import Github, InputFileContent


@pytest.mark.skipif("GITHUB_TOKEN" not in environ, reason="This is a development test, needs GITHUB_TOKEN")
def test_publish_gist():
    gh = Github(login_or_token=environ["GITHUB_TOKEN"])
    user = gh.get_user()
    gist = user.create_gist(public=False, files={"test": InputFileContent("foo", "new_name")})
    print(gist.html_url)
