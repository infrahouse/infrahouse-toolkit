"""
Module for :py:class:`GitHubPR`.
"""

from logging import getLogger
from os import environ
from typing import Union

from github import Github, InputFileContent
from github.GithubException import GithubException
from github.IssueComment import IssueComment

from infrahouse_toolkit.terraform import IHParseError, parse_comment
from infrahouse_toolkit.terraform.backends.tfbackend import TFBackend

LOG = getLogger()


class GitHubPR:
    """
    :py:class:`GitHubPR` represents a pull request on GitHub.
    The pull request is identified by a repository name and a pull request number.
    To access GitHub the class needs a GitHub token.
    All these are input arguments of the class.

    :param repo_name: Full repository name. For example, ``infrahouse/infrahouse-toolkit``.
    :typo repo_name: str
    :param pull_request: Pull request number.
    :type pull_request: int
    :param github_token: GitHub personal access tokens. They are created in
        https://github.com/settings/tokens
    :type github_token: str
    """

    def __init__(self, repo_name: str, pull_request: int, github_token: str = None):
        self._github_token = github_token
        self._repo_name = repo_name
        self._pr_number = pull_request

    @property
    def comments(self):
        """
        An interator with comments in this PR.
        """
        return self.pull_request.get_issue_comments()

    @property
    def github(self):
        """
        GitHub client.
        """
        return Github(login_or_token=self.github_token)

    @property
    def github_token(self):
        """
        GitHub token as passed by the class argument or from the ``GITHUB_TOKEN`` environment variable.
        If the ``GITHUB_TOKEN`` environment variable is not defined the property will return None.
        """
        return self._github_token if self._github_token else environ.get("GITHUB_TOKEN")

    @property
    def repo(self):
        """
        Repository object of the repository name passed in the class argument.
        """
        return self.github.get_repo(self._repo_name)

    @property
    def pull_request(self):
        """
        Pull request object of the repository name passed in the class argument.
        """
        return self.repo.get_pull(self._pr_number)

    def delete_my_comments(self):
        """
        Delete all comments in the pull request.
        """
        for comment in self.comments:
            comment.delete()

    def find_comment_by_backend(self, backend: TFBackend) -> Union[IssueComment, None]:
        """
        Find a comment that describes state of a given backend.
        It will return None if nothing is found.

        :param backend: Terraform Backend configuration.
        :return: a comment object or None.
        :rtype: IssueComment, None
        """
        for comment in self.comments:
            try:
                status = parse_comment(comment.body)
                if status.backend == backend:
                    return comment
            except IHParseError:
                pass
        return None

    def edit_comment(self, comment: IssueComment, new_text: str, private_gist: bool = True):
        """
        Modify existing comment. If the new comment is too big,
        publish it as a gist.
        """
        try:
            comment.edit(new_text)
        except GithubException as err:
            LOG.error(err)
            # https://docs.github.com/en/rest/issues/comments?apiVersion=2022-11-28#create-an-issue-comment
            if err.status == 422:  # Validation failed, or the endpoint has been spammed.
                gist = self._publish_gist(
                    f"pr-{self._pr_number}-plan",
                    f"{self._repo_name.replace('/', '-')}-pr-{self._pr_number}-plan.txt",
                    comment,
                    not private_gist,
                )
                comment.edit(f"Comment was too big. It's published as a gist at {gist.html_url}.")
            else:
                raise

    def publish_comment(self, comment: str, private_gist: bool = True):
        """Add the given text as a comment in the pull request."""
        try:
            self.pull_request.create_issue_comment(comment)
        except GithubException as err:
            LOG.error(err)
            # https://docs.github.com/en/rest/issues/comments?apiVersion=2022-11-28#create-an-issue-comment
            if err.status == 422:  # Validation failed, or the endpoint has been spammed.
                gist = self._publish_gist(
                    f"pr-{self._pr_number}-plan",
                    f"{self._repo_name.replace('/', '-')}-pr-{self._pr_number}-plan.txt",
                    comment,
                    not private_gist,
                )
                self.pull_request.create_issue_comment(
                    f"Comment was too big. It's published as a gist at {gist.html_url}."
                )
            else:
                raise

    def _publish_gist(self, gist_id, filename, content, public):
        current_user = self.github.get_user()
        return current_user.create_gist(
            public=public,
            files={
                gist_id: InputFileContent(
                    content=content,
                    new_name=filename,
                )
            },
        )
