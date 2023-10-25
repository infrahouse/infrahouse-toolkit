from os import environ
from unittest import mock
from unittest.mock import Mock, call

import pytest
from github import GithubException

from infrahouse_toolkit.terraform import RunOutput, TFStatus, parse_plan
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


def test_publish_too_large_comment():
    gh_pr = GitHubPR("foo/bar", 123)
    mock_pull_request = Mock()
    mock_pull_request.create_issue_comment.side_effect = [GithubException(422, "some data", {}), None]

    mock_gist = Mock()
    mock_gist.html_url = "gist url"
    with mock.patch.object(
        GitHubPR, "pull_request", new_callable=mock.PropertyMock, return_value=mock_pull_request
    ), mock.patch.object(GitHubPR, "_publish_gist", return_value=mock_gist) as mock_publish_gist:
        gh_pr.publish_comment("foo comment")
        mock_publish_gist.assert_called_once_with("pr-123-plan", "foo-bar-pr-123-plan.txt", "foo comment", False)
        mock_pull_request.create_issue_comment.assert_has_calls(
            [call("foo comment"), call("Comment was too big. It's published as a gist at gist url.")]
        )
