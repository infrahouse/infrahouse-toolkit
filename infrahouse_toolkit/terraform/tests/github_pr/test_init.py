from infrahouse_toolkit.terraform.githubpr import GitHubPR


def test_init():
    gh_pr = GitHubPR("infrahouse8/github-control", 33)
    for comment in gh_pr.comments:
        # 1/0
        print(comment.body)
