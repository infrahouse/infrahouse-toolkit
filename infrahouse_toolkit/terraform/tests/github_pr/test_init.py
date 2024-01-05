from os import environ

import pytest

from infrahouse_toolkit.terraform.githubpr import GitHubPR


@pytest.mark.skipif("GITHUB_TOKEN" not in environ, reason="This is a development test, needs GITHUB_TOKEN")
def test_init():
    gh_pr = GitHubPR("infrahouse8/github-control", 33)
    for comment in gh_pr.comments:
        # 1/0
        print(comment.body)
