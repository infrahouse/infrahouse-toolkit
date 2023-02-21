from os import environ

import pytest

from infrahouse_toolkit.terraform import RunOutput, TFStatus, parse_comment, parse_plan
from infrahouse_toolkit.terraform.backends import TFS3Backend
from infrahouse_toolkit.terraform.githubpr import GitHubPR


@pytest.mark.skipif("GITHUB_TOKEN" not in environ, reason="This is a development test, needs GITHUB_TOKEN")
def test_publish_comment():
    gh_pr = GitHubPR("infrahouse8/github-control", 33)
    gh_pr.delete_my_comments()
    counts, resources = parse_plan(open("infrahouse_toolkit/terraform/tests/plans/plan-2-1-2.stdout").read())
    status = TFStatus(
        TFS3Backend("foo-bucket", "path/to/key.state"),
        success=True,
        run_result=counts,
        run_output=RunOutput(open("infrahouse_toolkit/terraform/tests/plans/plan-2-1-2.stdout").read(), None),
        affected_resources=resources,
    )
    print(status.comment)
    gh_pr.publish_comment(status.comment)
