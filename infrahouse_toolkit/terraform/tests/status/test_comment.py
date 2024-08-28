import json
from base64 import b64decode
from os import path as osp

import pytest

from infrahouse_toolkit.terraform.backends import TFS3Backend
from infrahouse_toolkit.terraform.status import RunOutput, RunResult, TFStatus


@pytest.mark.parametrize(
    "plan_file, result_counts, expected_comment",
    [
        (
            "plan-no-output.stdout",
            (1, 1, 1),
            """
# State **`s3://foo_backet/path/to/tf.state`**
## Affected resources counts

|   Success |   🟢 Add |   🟡 Change |   🔴 Destroy |
|----------:|---------:|------------:|-------------:|
|        ✅ |        1 |           1 |            1 |
<details>
<summary>STDOUT</summary>

```
no stdout
```
</details>
<details><summary><i>metadata</i></summary>

```
eyJzMzovL2Zvb19iYWNrZXQvcGF0aC90by90Zi5zdGF0ZSI6IHsic3VjY2VzcyI6IHRydWUsICJhZGQiOiAxLCAiY2hhbmdlIjogMSwgImRlc3Ryb3kiOiAxfX0=
```
</details>""",
        ),
        (
            "plan-0-0-0.stdout",
            (0, 0, 0),
            """
# State **`s3://foo_backet/path/to/tf.state`**
## Affected resources counts

|   Success |    Add |    Change |    Destroy |
|----------:|-------:|----------:|-----------:|
|        ✅ |      0 |         0 |          0 |
<details>
<summary>STDOUT</summary>

```
Terraform has compared your real infrastructure against your configuration
and found no differences, so no changes are needed.
```
</details>
<details><summary><i>metadata</i></summary>

```
eyJzMzovL2Zvb19iYWNrZXQvcGF0aC90by90Zi5zdGF0ZSI6IHsic3VjY2VzcyI6IHRydWUsICJhZGQiOiAwLCAiY2hhbmdlIjogMCwgImRlc3Ryb3kiOiAwfX0=
```
</details>""",
        ),
        (
            "plan-2-0-0.stdout",
            (2, 0, 0),
            """
# State **`s3://foo_backet/path/to/tf.state`**
## Affected resources counts

|   Success |   🟢 Add |    Change |    Destroy |
|----------:|---------:|----------:|-----------:|
|        ✅ |        2 |         0 |          0 |
<details>
<summary>STDOUT</summary>

```
Terraform used the selected providers to generate the following execution
plan. Resource actions are indicated with the following symbols:
  + create

Terraform will perform the following actions:

  # module.repos["test"].github_repository.repo will be created
  + resource "github_repository" "repo" {
      + allow_auto_merge            = false
      + allow_merge_commit          = true
      + allow_rebase_merge          = true
      + allow_squash_merge          = true
      + archived                    = false
      + default_branch              = (known after apply)
      + delete_branch_on_merge      = false
      + description                 = "Template for a GitHub Control repository"
      + etag                        = (known after apply)
      + full_name                   = (known after apply)
      + git_clone_url               = (known after apply)
      + has_issues                  = true
      + html_url                    = (known after apply)
      + http_clone_url              = (known after apply)
      + id                          = (known after apply)
      + merge_commit_message        = "PR_TITLE"
      + merge_commit_title          = "MERGE_MESSAGE"
      + name                        = "test"
      + node_id                     = (known after apply)
      + private                     = (known after apply)
      + repo_id                     = (known after apply)
      + squash_merge_commit_message = "COMMIT_MESSAGES"
      + squash_merge_commit_title   = "COMMIT_OR_PR_TITLE"
      + ssh_clone_url               = (known after apply)
      + svn_url                     = (known after apply)
      + visibility                  = "public"

      + security_and_analysis {
          + advanced_security {
              + status = (known after apply)
            }

          + secret_scanning {
              + status = (known after apply)
            }

          + secret_scanning_push_protection {
              + status = (known after apply)
            }
        }
    }

  # module.repos["test"].github_team_repository.dev will be created
  + resource "github_team_repository" "dev" {
      + etag       = (known after apply)
      + id         = (known after apply)
      + permission = "push"
      + repository = "test"
      + team_id    = "7332815"
    }

Plan: 2 to add, 0 to change, 0 to destroy.

─────────────────────────────────────────────────────────────────────────────

Saved the plan to: tf.plan

To perform exactly these actions, run the following command to apply:
    terraform apply "tf.plan"
```
</details>
<details><summary><i>metadata</i></summary>

```
eyJzMzovL2Zvb19iYWNrZXQvcGF0aC90by90Zi5zdGF0ZSI6IHsic3VjY2VzcyI6IHRydWUsICJhZGQiOiAyLCAiY2hhbmdlIjogMCwgImRlc3Ryb3kiOiAwfX0=
```
</details>""",
        ),
        (
            "plan-2-1-2.stdout",
            (2, 1, 2),
            """
# State **`s3://foo_backet/path/to/tf.state`**
## Affected resources counts

|   Success |   🟢 Add |   🟡 Change |   🔴 Destroy |
|----------:|---------:|------------:|-------------:|
|        ✅ |        2 |           1 |            2 |
<details>
<summary>STDOUT</summary>

```
Terraform used the selected providers to generate the following execution
plan. Resource actions are indicated with the following symbols:
  + create
  ~ update in-place
  - destroy

Terraform will perform the following actions:

  # module.repos["cookiecutter-github-control"].github_repository.repo will be destroyed
  # (because module.repos["cookiecutter-github-control"] is not in configuration)
  - resource "github_repository" "repo" {
      - allow_auto_merge            = false -> null
      - allow_merge_commit          = true -> null
      - allow_rebase_merge          = true -> null
      - allow_squash_merge          = true -> null
      - allow_update_branch         = false -> null
      - archived                    = false -> null
      - default_branch              = "main" -> null
      - delete_branch_on_merge      = false -> null
      - description                 = "Template for a GitHub Control repository" -> null
      - etag                        = "W/\\\"8b4a792bc1474d381caaa63b76668993b4adc42ae76ed53d6886d8562ebb0c67\\\"" -> null
      - full_name                   = "infrahouse/cookiecutter-github-control" -> null
      - git_clone_url               = "git://github.com/infrahouse/cookiecutter-github-control.git" -> null
      - has_discussions             = false -> null
      - has_downloads               = false -> null
      - has_issues                  = true -> null
      - has_projects                = false -> null
      - has_wiki                    = false -> null
      - html_url                    = "https://github.com/infrahouse/cookiecutter-github-control" -> null
      - http_clone_url              = "https://github.com/infrahouse/cookiecutter-github-control.git" -> null
      - id                          = "cookiecutter-github-control" -> null
      - is_template                 = false -> null
      - merge_commit_message        = "PR_TITLE" -> null
      - merge_commit_title          = "MERGE_MESSAGE" -> null
      - name                        = "cookiecutter-github-control" -> null
      - node_id                     = "R_kgDOI528zg" -> null
      - private                     = false -> null
      - repo_id                     = 597540046 -> null
      - squash_merge_commit_message = "COMMIT_MESSAGES" -> null
      - squash_merge_commit_title   = "COMMIT_OR_PR_TITLE" -> null
      - ssh_clone_url               = "git@github.com:infrahouse/cookiecutter-github-control.git" -> null
      - svn_url                     = "https://github.com/infrahouse/cookiecutter-github-control" -> null
      - topics                      = [] -> null
      - visibility                  = "public" -> null
      - vulnerability_alerts        = false -> null

      - security_and_analysis {

          - secret_scanning {
              - status = "disabled" -> null
            }

          - secret_scanning_push_protection {
              - status = "disabled" -> null
            }
        }
    }

  # module.repos["cookiecutter-github-control"].github_team_repository.dev will be destroyed
  # (because module.repos["cookiecutter-github-control"] is not in configuration)
  - resource "github_team_repository" "dev" {
      - etag       = "W/\\\"8043f81b19693f6c1a72d21bb8dc03859c98bf78bfbe79782bfe13fa813992ca\\\"" -> null
      - id         = "7332815:cookiecutter-github-control" -> null
      - permission = "push" -> null
      - repository = "cookiecutter-github-control" -> null
      - team_id    = "7332815" -> null
    }

  # module.repos["infrahouse-toolkit"].github_repository.repo will be updated in-place
  ~ resource "github_repository" "repo" {
      ~ description                 = "InfraHouse Toolkit" -> "InfraHouse Toolkit1"
        id                          = "infrahouse-toolkit"
        name                        = "infrahouse-toolkit"
        # (31 unchanged attributes hidden)

        # (1 unchanged block hidden)
    }

  # module.repos["test"].github_repository.repo will be created
  + resource "github_repository" "repo" {
      + allow_auto_merge            = false
      + allow_merge_commit          = true
      + allow_rebase_merge          = true
      + allow_squash_merge          = true
      + archived                    = false
      + default_branch              = (known after apply)
      + delete_branch_on_merge      = false
      + description                 = "Template for a GitHub Control repository"
      + etag                        = (known after apply)
      + full_name                   = (known after apply)
      + git_clone_url               = (known after apply)
      + has_issues                  = true
      + html_url                    = (known after apply)
      + http_clone_url              = (known after apply)
      + id                          = (known after apply)
      + merge_commit_message        = "PR_TITLE"
      + merge_commit_title          = "MERGE_MESSAGE"
      + name                        = "test"
      + node_id                     = (known after apply)
      + private                     = (known after apply)
      + repo_id                     = (known after apply)
      + squash_merge_commit_message = "COMMIT_MESSAGES"
      + squash_merge_commit_title   = "COMMIT_OR_PR_TITLE"
      + ssh_clone_url               = (known after apply)
      + svn_url                     = (known after apply)
      + visibility                  = "public"

      + security_and_analysis {
          + advanced_security {
              + status = (known after apply)
            }

          + secret_scanning {
              + status = (known after apply)
            }

          + secret_scanning_push_protection {
              + status = (known after apply)
            }
        }
    }

  # module.repos["test"].github_team_repository.dev will be created
  + resource "github_team_repository" "dev" {
      + etag       = (known after apply)
      + id         = (known after apply)
      + permission = "push"
      + repository = "test"
      + team_id    = "7332815"
    }

Plan: 2 to add, 1 to change, 2 to destroy.

─────────────────────────────────────────────────────────────────────────────

Saved the plan to: tf.plan

To perform exactly these actions, run the following command to apply:
    terraform apply "tf.plan"
```
</details>
<details><summary><i>metadata</i></summary>

```
eyJzMzovL2Zvb19iYWNrZXQvcGF0aC90by90Zi5zdGF0ZSI6IHsic3VjY2VzcyI6IHRydWUsICJhZGQiOiAyLCAiY2hhbmdlIjogMSwgImRlc3Ryb3kiOiAyfX0=
```
</details>""",
        ),
    ],
)
def test_comment(plan_file, result_counts, expected_comment):
    with open(osp.join("infrahouse_toolkit/terraform/tests/plans", plan_file)) as fp:
        status = TFStatus(
            TFS3Backend("foo_backet", "path/to/tf.state"), True, RunResult(*result_counts), RunOutput(fp.read(), None)
        )
        assert isinstance(status.comment, str)
        print("\nActual comment:")
        print(status.comment)
        print("EOF Actual comment.")
        assert status.comment == expected_comment


def test_comment_none():
    status = TFStatus(
        TFS3Backend("foo_backet", "path/to/tf.state"),
        True,
        RunResult(None, None, None),
        RunOutput("no stdout", "no stderr"),
        affected_resources=RunResult(None, None, None),
    )
    assert isinstance(status.comment, str)
    print(status.comment)
