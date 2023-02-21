from os import environ

import pytest

from infrahouse_toolkit.terraform import parse_comment, parse_plan
from infrahouse_toolkit.terraform.backends import TFS3Backend
from infrahouse_toolkit.terraform.githubpr import GitHubPR


@pytest.mark.skipif("GITHUB_TOKEN" not in environ, reason="This is a development test, needs GITHUB_TOKEN")
def test_find_comment_by_backend():
    gh_pr = GitHubPR("infrahouse8/github-control", 33)
    comment = gh_pr.find_comment_by_backend(TFS3Backend("foo-bucket", "path/to/key.state"))
    if comment:
        status = parse_comment(comment.body)
        counts, resources = parse_plan(open("infrahouse_toolkit/terraform/tests/plans/plan-2-1-2.stdout").read())
        status.affected_resources = resources
        status.add = counts.add
        status.change = counts.change
        status.destroy = counts.destroy
        status.success = False
        print(status.comment)

        comment.edit(status.comment)
