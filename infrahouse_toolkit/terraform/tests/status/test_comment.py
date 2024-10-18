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
        (
            "plan-0-2-0-a.stdout",
            (0, 2, 0),
            """
# State **`s3://foo_backet/path/to/tf.state`**
## Affected resources counts

|   Success |    Add |   🟡 Change |    Destroy |
|----------:|-------:|------------:|-----------:|
|        ✅ |      0 |           2 |          0 |
<details>
<summary>STDOUT</summary>

```
Terraform used the selected providers to generate the following execution
plan. Resource actions are indicated with the following symbols:
  ~ update in-place

Terraform will perform the following actions:

  # module.website.aws_autoscaling_group.website will be updated in-place
  ~ resource "aws_autoscaling_group" "website" {
        id                               = "web20231125205239428700000003"
        name                             = "web20231125205239428700000003"
        # (32 unchanged attributes hidden)

      ~ launch_template {
            id      = "lt-042ea5dd55b0fff3b"
            name    = "web20231125205151213200000001"
          ~ version = "8" -> (known after apply)
        }

        # (9 unchanged blocks hidden)
    }

  # module.website.aws_launch_template.website will be updated in-place
  ~ resource "aws_launch_template" "website" {
        id                                   = "lt-042ea5dd55b0fff3b"
      ~ latest_version                       = 8 -> (known after apply)
        name                                 = "web20231125205151213200000001"
        tags                                 = {}
      ~ user_data                            = "Q29udGVudC1UeXBlOiBtdWx0aXBhcnQvbWl4ZWQ7IGJvdW5kYXJ5PSJNSU1FQk9VTkRBUlkiCk1JTUUtVmVyc2lvbjogMS4wDQoNCi0tTUlNRUJPVU5EQVJZDQpDb250ZW50LVRyYW5zZmVyLUVuY29kaW5nOiA3Yml0DQpDb250ZW50LVR5cGU6IHRleHQvY2xvdWQtY29uZmlnDQpNaW1lLVZlcnNpb246IDEuMA0KDQojY2xvdWQtY29uZmlnCiJhcHQiOgogICJzb3VyY2VzIjoKICAgICJpbmZyYWhvdXNlIjoKICAgICAgImtleSI6IHwKICAgICAgICAtLS0tLUJFR0lOIFBHUCBQVUJMSUMgS0VZIEJMT0NLLS0tLS0KCiAgICAgICAgbVFJTkJHUzdGdGtCRUFERitZbURnNlF2c3Y1VjZaUXcrUWh4ZFR2ak1YZUxDOVQ2UkZSVkQ5NDdxS3p0Tk5RbgogICAgICAgICtBL3l4cHJMQW1XMjVVdS8xMW9Dc3pOVklJYVIzT1k4TXR5aWxiQ3R6VWtCenZXZGxYM0h2VHc5MUxwOGJ4VUwKICAgICAgICBFWE9NOW5zY3FPck92ZkJqYW5wbEtERUtQTVk2dklaM2twMXJVc0NOR0xCTDB4MktaZ1U4MHVsUnNNTThxbkJOCiAgICAgICAga3BUaUFlWEtPRVZ0UnpsV2x2T0ZMSjdwWUR2YVowVWdIU1Z1RStaa2xkcU9kTExScEtrZEl2SlBja1hxTDV4VAogICAgICAgIFV2V1RXMWVuRkFIZDUrTlF4TW5DYTNpa2pRVjNEVGxFanNnTExRYmJ5c1hqWFByNlBJUHMyOWNUY2ZvcTQzMU8KICAgICAgICB0UjREclpCNHZNRU9BODhUbUtCa0VpTUcraUI5Y2p6NXdCSXVNdTk1Wm1vSnhkdmpQUjcyRllLZ3JDWE50TmhkCiAgICAgICAgVmVyRVJ2cExUaGRhUm1aZ2k3bHkrRHZrWTdMcXlKUHZkSGNxeGVkZ0ZuUEtSNFQrZ1NRbWJVUGQ5cXFkSlIwUQogICAgICAgIEtsL1BtdHVTL3c5Z3kyWjRheTBRSUtyTkJ6UXhoQThMRFpwcDFydWZDSjUrWk1lZjkwdkhwd3hNK09hUHJ5TmwKICAgICAgICBFZERXN1lROGZ1QjVuUHFqd1VBcG1sWVlMSllsZDd2Sjc5RUl4L3NqZ2g2RytJRmltN3hSN1dpUUYvbkpldmZxCiAgICAgICAgdnpZTzdvci9HSUNiNmVad3ZQZHR5NzlIbVZlUHFFVGxEVTAwb3lvcFd5VHNZeVNZRFNIbi80ZG9UdXg4ditGLwogICAgICAgIFlleWJ2Z3FicmlIN2lTRjhIeHdFRmVEanJNdFVUSHNYQzM1REhGZU1DaEpveHN5S3Y0OEorYklHRndBUkFRQUIKICAgICAgICB0QzFKYm1aeVlVaHZkWE5sSUZCaFkydGhaMlZ5SUR4d1lXTnJZV2RsY2tCcGJtWnlZV2h2ZFhObExtTnZiVDZKCiAgICAgICAgQWxRRUV3RUtBRDRXSVFTaU5oNWtZM3c4VzBnQUY4WGd1SmFveGZjRDd3VUNaTHNXMlFJYkF3VUpBOEpuQUFVTAogICAgICAgIENRZ0hBZ1lWQ2drSUN3SUVGZ0lEQVFJZUFRSVhnQUFLQ1JEZ3VKYW94ZmNEN3diN0QvOWVuYnRPMURFUW4xUHQKICAgICAgICBoZ2t0SCtJcmJCZFlSSGs3MWlsMmhibm1BYm9Ma2sxYWsvYWFRWS9YUURKRmhyQTdqTWtQTE9DUmVvdEhpUW12CiAgICAgICAgMVVmcURjTTJlUTQveDBOOUYyRExVU2t1d3cxMTd2dHRVb0J4aXJCNzJwTzBUL2xkOW8zOVNITUMvRGZrNnk2aAogICAgICAgIHRUR3F4TGdoOGozRFN5TzVFRXJKTGEvM0J2TXFyNGlxYjNQVHdOZURSRWphdlFKaFhTdkVGanlBQ29vOWQ3cnMKICAgICAgICA3bGhDYmJTUGpnVGNHL1BDZnpMcjM3UXl6WGlUUi9Ud2ppd1ZkVGhkQ1MvQ0tuc29NOG5nSHhqWFlwSzdNNndnCiAgICAgICAgdHpBOEprSFpyNU1wa3JQR3JnUWV2aEpCTGtIUi9qY3NhYUJaTjdudzhhZUhjd3dNNC9DaEhJeVpkUTkxMDU5cAogICAgICAgIE9NYVltV21qUFFmcTFyT25BQXZBMXhXdytUWk56SGdXSXE0dnVzeDdPQnZyRnNWZVpOc3FkN09hNHBydFZXZzAKICAgICAgICA5MWNLWkpvL092Nm9wTS93RFdOMnlCbmttQkN3YVhwb0g1TkRRMjJiaG5HVEplSVdkZWk4VVNHcHZCa1R4QkkyCiAgICAgICAgWDMycHlPbVpEbjgxTDJ6TTJpb052Z1hJYjV1NXRqYjlOT2lBdDZvVzBHMHgwMGRncjNyNnB1OHFtTXdrQlZCQwogICAgICAgIHZXd0VtYXhRbmtUaG5iQWQ1N1ZiYXQ0Ly91RGNIRnBEYUJQcEZXZUNMMmRmRFNyUzlpaUs2SzFWa3ZHTG9YaDgKICAgICAgICBNcEpxam9kZHBmTmg0dXlmekt5TkUxZHJRMjltY3dmSWx6WG9QcmIwOVc2WkhwbSt0cWQ4TWs3MDd6d3NkRkdSCiAgICAgICAgcVJzeG10UG45SjFyZVlaaVZ1RTVHMjZmMWFLVFI3a0NEUVJrdXhiWkFSQUE0KzlrbjRzbUJYWmNNMHZGcTlSOAogICAgICAgIDI0WEtadFRhVm1Wb1ZKTVJRTTQ0cVdSK3MvUzBNenZiTzV1MGNTVlRoWTY1WXpNTHM5MjBVWTZ1R3BvUzJaWXcKICAgICAgICBJTWlwa2FCKzJGNkI4UjdWN25sL1NnYVhHYTJNZXhrQzd3dDZibEZiYXc3cGJ2SStpSTl3UzhCS0hnTUR6ZDBGCiAgICAgICAgVGpTcTl2ZGtWa2Y3eUkzaEV3bGxYN3pUNklMT3Zrbk5HYm9zMGRGSTkyY0JXUXMraVhQNTB4RFZpdDMrOW1DRAogICAgICAgIHJ1V1ZZazczbXZTRXpGY3VYQ3liS0o1VS9uelNRNzBKb1FtU1BjNTBSUWp1SEdkemwvWXpHRmFGbjV6SVo1cFAKICAgICAgICBrNVMrS1RZZWt6Y2lSa0h6YmVhNVBqK0E2S1ppbEtqNXlrQVJGencrQ1B4cXN1ZWpEa2k3QSthM20zV0dxK21tCiAgICAgICAgQWtsUTRZQmNvbHpOT3BnV2NsSVN1RTNkNWtndGFKQUNJZ3RlODdGNlFCQnNrOG9EQkZRQ25abW9PaXJsU2xiZgogICAgICAgIEp1RDZmVkNKdTJ6WTdUaE4xTzBvV1R3QWFOQXZNNTVDTFR2NnMzRm10UjkybG5sUURGdUorZmo4NjNjNnF4MTQKICAgICAgICBGdU80bU03ZXVTMDh3R2dWR205MXdBN2JZbDRhaHhDNlMyQkdCNUZ2a1pmekJCd2pzZm1VV0hBdTdWUlpKeGtYCiAgICAgICAgSnA2OTZPVGRSM1JmSTdJWjZPVzZ0R0VMaWpzd1diYlpYYjVYUldFVzk5dldPN05JSzZzT3ZoTUROcDliU011YgogICAgICAgIFhQM1BiUHhneVQwYm1zczB5d05Zd3VjbmZjbURYcVBWdTNHZHQ1M2F0MStoSzdtbG5RM3VVczVlVkVPSUhuSm0KICAgICAgICBmMXRyRGdnU1RFN2Zua3g2Q3psK2lNa0FFUUVBQVlrQ1BBUVlBUW9BSmhZaEJLSTJIbVJqZkR4YlNBQVh4ZUM0CiAgICAgICAgbHFqRjl3UHZCUUprdXhiWkFoc01CUWtEd21jQUFBb0pFT0M0bHFqRjl3UHY4U1FQL2pzUWZKQ1VIcmpwWDRmUAogICAgICAgIDBOdFZ5cWxDcnExT21MUDdCTHJYckN4b0FGUmI2NFlKVWRXazVQMzVrOXdqMkJRanBqY05qMmlrODBGb28wMkUKICAgICAgICB5YytQelcvNHR6VnZkeFJyRXpzT0ZtK21NUitsbFVIQUt6QmE2UUJ4SFQwb2ZMN3A1WFlUdU1ObllvK1BqVk1tCiAgICAgICAgalAzVEVKR1lYWW11aEdmYWFKWnBqTG1KRnFwNTl4Ly9kc01IZUxxVUNod2I2Q2c2RHVrQWloZUFzM1ArclhvMwogICAgICAgIHRCbkE0SkNDaVhSNy8vMFdlelJvU1BkYWxOZW00dnM4UFQ4N3NuSGJEbGlGTVZmOHcrZmtzSW5xdm90aVJESTQKICAgICAgICBRQnJCZnMzTmRlWlcvdG11cE9hWkpSekhEdnZLYmcvL082aXAxYVB2SUxXdlRETThLY1FDUUVTYVdrQ2JJMXVjCiAgICAgICAgcml6QU1ibFRCMmd5dzl5b2pDcFZDTUJYZGl6QXFxeWw1WlZydzQrWC9pMDlJc050OGhBOS81Ulk3djNjN1oyQwogICAgICAgIFh5MnhLV210TEk5bmxPU1N3VXhCNTY2STI5bFZLQkxVbVhtUWZuUklJSENpSkRYWUZEUC82TGZ2OSttaEVXVTgKICAgICAgICBxZWQzeGhwZU5TQUl6QStNVGxqdGlSbW9yeHBkZGlYYnRDYWZjUGwvSjNYMEIwN2ZjY0pad1pzQ1lDcHRMeTFjCiAgICAgICAgeXZWYU4rRUJtam9DcDNqdDZ3TGU0eGNscVUzQUN3ei84VEREbXRKN1VVZGw3TWRraXBRWjI3OEwya3BsNm82MQogICAgICAgIE1GMmZYRDdmWk1lWmZFdzZsdTBCRjVtWjAvY2gzSHhYZVpvWGlmNzlnMjV2Wm1TZFc5N3BjZWV3UGx2bEVURlEKICAgICAgICA1NXBNb3JReVVURVFDUTNFQ3pIWVNuTC9UbVc3CiAgICAgICAgPSswUmMKICAgICAgICAtLS0tLUVORCBQR1AgUFVCTElDIEtFWSBCTE9DSy0tLS0tCiAgICAgICJzb3VyY2UiOiAiZGViIFtzaWduZWQtYnk9JEtFWV9GSUxFXSBodHRwczovL3JlbGVhc2UtamFtbXkuaW5mcmFob3VzZS5jb20vICRSRUxFQVNFCiAgICAgICAgbWFpbiIKInBhY2thZ2VfdXBkYXRlIjogdHJ1ZQoicGFja2FnZXMiOgotICJtYWtlIgotICJnY2MiCi0gInB1cHBldC1jb2RlIgotICJpbmZyYWhvdXNlLXRvb2xraXQiCi0gImluZnJhaG91c2UtcHVwcGV0LWRhdGEiCiJwdXBwZXQiOgogICJjb2xsZWN0aW9uIjogInB1cHBldDgiCiAgImluc3RhbGwiOiB0cnVlCiAgImluc3RhbGxfdHlwZSI6ICJhaW8iCiAgInBhY2thZ2VfbmFtZSI6ICJwdXBwZXQtYWdlbnQiCiAgInN0YXJ0X3NlcnZpY2UiOiBmYWxzZQoicnVuY21kIjoKLSAiL29wdC9wdXBwZXRsYWJzL3B1cHBldC9iaW4vZ2VtIGluc3RhbGwganNvbiIKLSAiL29wdC9wdXBwZXRsYWJzL3B1cHBldC9iaW4vZ2VtIGluc3RhbGwgYXdzLXNkay1jb3JlIgotICIvb3B0L3B1cHBldGxhYnMvcHVwcGV0L2Jpbi9nZW0gaW5zdGFsbCBhd3Mtc2RrLXNlY3JldHNtYW5hZ2VyIgotICJpaC1wdXBwZXQgIC0tZW52aXJvbm1lbnQgcHJvZHVjdGlvbiAtLWVudmlyb25tZW50cGF0aCB7cm9vdF9kaXJlY3Rvcnl9L2Vudmlyb25tZW50cwogIC0tcm9vdC1kaXJlY3RvcnkgL29wdC9wdXBwZXQtY29kZSAtLWhpZXJhLWNvbmZpZyAvb3B0L2luZnJhaG91c2UtcHVwcGV0LWRhdGEvZW52aXJvbm1lbnRzL3Byb2R1Y3Rpb24vaGllcmEueWFtbAogIC0tbW9kdWxlLXBhdGgge3Jvb3RfZGlyZWN0b3J5fS9tb2R1bGVzIGFwcGx5IC9vcHQvcHVwcGV0LWNvZGUvZW52aXJvbm1lbnRzL3Byb2R1Y3Rpb24vbWFuaWZlc3RzL3NpdGUucHAiCiJ3cml0ZV9maWxlcyI6Ci0gImNvbnRlbnQiOiAiZXhwb3J0IEFXU19ERUZBVUxUX1JFR0lPTj11cy13ZXN0LTEiCiAgInBhdGgiOiAiL2V0Yy9wcm9maWxlLmQvYXdzLnNoIgogICJwZXJtaXNzaW9ucyI6ICIwNjQ0IgotICJjb250ZW50IjogfC0KICAgIFtkZWZhdWx0XQogICAgcmVnaW9uPXVzLXdlc3QtMQogICJwYXRoIjogIi9yb290Ly5hd3MvY29uZmlnIgogICJwZXJtaXNzaW9ucyI6ICIwNjAwIgotICJjb250ZW50IjogfAogICAgInB1cHBldF9lbnZpcm9ubWVudCI6ICJwcm9kdWN0aW9uIgogICAgInB1cHBldF9yb2xlIjogIndlYnNlcnZlciIKICAicGF0aCI6ICIvZXRjL3B1cHBldGxhYnMvZmFjdGVyL2ZhY3RzLmQvcHVwcGV0LnlhbWwiCiAgInBlcm1pc3Npb25zIjogIjA2NDQiCi0gImNvbnRlbnQiOiAie1wiaWgtcHVwcGV0XCI6e1wiZGVidWdcIjpmYWxzZSxcImVudmlyb25tZW50cGF0aFwiOlwie3Jvb3RfZGlyZWN0b3J5fS9lbnZpcm9ubWVudHNcIixcImhpZXJhLWNvbmZpZ1wiOlwiL29wdC9pbmZyYWhvdXNlLXB1cHBldC1kYXRhL2Vudmlyb25tZW50cy9wcm9kdWN0aW9uL2hpZXJhLnlhbWxcIixcIm1hbmlmZXN0XCI6XCIvb3B0L3B1cHBldC1jb2RlL2Vudmlyb25tZW50cy9wcm9kdWN0aW9uL21hbmlmZXN0cy9zaXRlLnBwXCIsXCJtb2R1bGUtcGF0aFwiOlwie3Jvb3RfZGlyZWN0b3J5fS9tb2R1bGVzXCIsXCJyb290LWRpcmVjdG9yeVwiOlwiL29wdC9wdXBwZXQtY29kZVwifX0iCiAgInBhdGgiOiAiL2V0Yy9wdXBwZXRsYWJzL2ZhY3Rlci9mYWN0cy5kL2loLXB1cHBldC5qc29uIgogICJwZXJtaXNzaW9ucyI6ICIwNjQ0IgotICJjb250ZW50IjogInt9IgogICJwYXRoIjogIi9ldGMvcHVwcGV0bGFicy9mYWN0ZXIvZmFjdHMuZC9jdXN0b20uanNvbiIKICAicGVybWlzc2lvbnMiOiAiMDY0NCIKDQotLU1JTUVCT1VOREFSWS0tDQo=" -> (known after apply)
userdata changes:
--- before
+++ after
@@ -1,109 +1 @@
-Content-Type: multipart/mixed; boundary="MIMEBOUNDARY"
-MIME-Version: 1.0
-
---MIMEBOUNDARY
-Content-Transfer-Encoding: 7bit
-Content-Type: text/cloud-config
-Mime-Version: 1.0
-
-#cloud-config
-"apt":
-  "sources":
-    "infrahouse":
-      "key": |
-        -----BEGIN PGP PUBLIC KEY BLOCK-----
-
-        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
-        55pMorQyUTEQCQ3ECzHYSnL/TmW7
-        =+0Rc
-        -----END PGP PUBLIC KEY BLOCK-----
-      "source": "deb [signed-by=$KEY_FILE] https://release-jammy.infrahouse.com/ $RELEASE
-        main"
-"package_update": true
-"packages":
-- "make"
-- "gcc"
-- "puppet-code"
-- "infrahouse-toolkit"
-- "infrahouse-puppet-data"
-"puppet":
-  "collection": "puppet8"
-  "install": true
-  "install_type": "aio"
-  "package_name": "puppet-agent"
-  "start_service": false
-"runcmd":
-- "/opt/puppetlabs/puppet/bin/gem install json"
-- "/opt/puppetlabs/puppet/bin/gem install aws-sdk-core"
-- "/opt/puppetlabs/puppet/bin/gem install aws-sdk-secretsmanager"
-- "ih-puppet  --environment production --environmentpath {root_directory}/environments
-  --root-directory /opt/puppet-code --hiera-config /opt/infrahouse-puppet-data/environments/production/hiera.yaml
-  --module-path {root_directory}/modules apply /opt/puppet-code/environments/production/manifests/site.pp"
-"write_files":
-- "content": "export AWS_DEFAULT_REGION=us-west-1"
-  "path": "/etc/profile.d/aws.sh"
-  "permissions": "0644"
-- "content": |-
-    [default]
-    region=us-west-1
-  "path": "/root/.aws/config"
-  "permissions": "0600"
-- "content": |
-    "puppet_environment": "production"
-    "puppet_role": "webserver"
-  "path": "/etc/puppetlabs/facter/facts.d/puppet.yaml"
-  "permissions": "0644"
-- "content": "{\\"ih-puppet\\":{\\"debug\\":false,\\"environmentpath\\":\\"{root_directory}/environments\\",\\"hiera-config\\":\\"/opt/infrahouse-puppet-data/environments/production/hiera.yaml\\",\\"manifest\\":\\"/opt/puppet-code/environments/production/manifests/site.pp\\",\\"module-path\\":\\"{root_directory}/modules\\",\\"root-directory\\":\\"/opt/puppet-code\\"}}"
-  "path": "/etc/puppetlabs/facter/facts.d/ih-puppet.json"
-  "permissions": "0644"
-- "content": "{}"
-  "path": "/etc/puppetlabs/facter/facts.d/custom.json"
-  "permissions": "0644"
-
---MIMEBOUNDARY--
+(known after apply)
EOF userdata changes.
        # (16 unchanged attributes hidden)

      + metadata_options {
          + http_tokens = "required"
        }

        # (4 unchanged blocks hidden)
    }

Plan: 0 to add, 2 to change, 0 to destroy.

─────────────────────────────────────────────────────────────────────────────

Saved the plan to: tf.plan

To perform exactly these actions, run the following command to apply:
    terraform apply "tf.plan"
```
</details>
<details><summary><i>metadata</i></summary>

```
eyJzMzovL2Zvb19iYWNrZXQvcGF0aC90by90Zi5zdGF0ZSI6IHsic3VjY2VzcyI6IHRydWUsICJhZGQiOiAwLCAiY2hhbmdlIjogMiwgImRlc3Ryb3kiOiAwfX0=
```
</details>""",
        ),
        (
            "plan-0-2-0.stdout",
            (0, 2, 0),
            """
# State **`s3://foo_backet/path/to/tf.state`**
## Affected resources counts

|   Success |    Add |   🟡 Change |    Destroy |
|----------:|-------:|------------:|-----------:|
|        ✅ |      0 |           2 |          0 |
<details>
<summary>STDOUT</summary>

```
Terraform used the selected providers to generate the following execution
plan. Resource actions are indicated with the following symbols:
  ~ update in-place

Terraform will perform the following actions:

  # module.website.aws_autoscaling_group.website will be updated in-place
  ~ resource "aws_autoscaling_group" "website" {
        id                               = "web20231125205239428700000003"
        name                             = "web20231125205239428700000003"
        # (32 unchanged attributes hidden)

      ~ launch_template {
            id      = "lt-042ea5dd55b0fff3b"
            name    = "web20231125205151213200000001"
          ~ version = "8" -> (known after apply)
        }

        # (9 unchanged blocks hidden)
    }

  # module.website.aws_launch_template.website will be updated in-place
  ~ resource "aws_launch_template" "website" {
        id                                   = "lt-042ea5dd55b0fff3b"
      ~ latest_version                       = 8 -> (known after apply)
        name                                 = "web20231125205151213200000001"
        tags                                 = {}
      ~ user_data                            = "Q29udGVudC1UeXBlOiBtdWx0aXBhcnQvbWl4ZWQ7IGJvdW5kYXJ5PSJNSU1FQk9VTkRBUlkiCk1JTUUtVmVyc2lvbjogMS4wDQoNCi0tTUlNRUJPVU5EQVJZDQpDb250ZW50LVRyYW5zZmVyLUVuY29kaW5nOiA3Yml0DQpDb250ZW50LVR5cGU6IHRleHQvY2xvdWQtY29uZmlnDQpNaW1lLVZlcnNpb246IDEuMA0KDQojY2xvdWQtY29uZmlnCiJhcHQiOgogICJzb3VyY2VzIjoKICAgICJpbmZyYWhvdXNlIjoKICAgICAgImtleSI6IHwKICAgICAgICAtLS0tLUJFR0lOIFBHUCBQVUJMSUMgS0VZIEJMT0NLLS0tLS0KCiAgICAgICAgbVFJTkJHUzdGdGtCRUFERitZbURnNlF2c3Y1VjZaUXcrUWh4ZFR2ak1YZUxDOVQ2UkZSVkQ5NDdxS3p0Tk5RbgogICAgICAgICtBL3l4cHJMQW1XMjVVdS8xMW9Dc3pOVklJYVIzT1k4TXR5aWxiQ3R6VWtCenZXZGxYM0h2VHc5MUxwOGJ4VUwKICAgICAgICBFWE9NOW5zY3FPck92ZkJqYW5wbEtERUtQTVk2dklaM2twMXJVc0NOR0xCTDB4MktaZ1U4MHVsUnNNTThxbkJOCiAgICAgICAga3BUaUFlWEtPRVZ0UnpsV2x2T0ZMSjdwWUR2YVowVWdIU1Z1RStaa2xkcU9kTExScEtrZEl2SlBja1hxTDV4VAogICAgICAgIFV2V1RXMWVuRkFIZDUrTlF4TW5DYTNpa2pRVjNEVGxFanNnTExRYmJ5c1hqWFByNlBJUHMyOWNUY2ZvcTQzMU8KICAgICAgICB0UjREclpCNHZNRU9BODhUbUtCa0VpTUcraUI5Y2p6NXdCSXVNdTk1Wm1vSnhkdmpQUjcyRllLZ3JDWE50TmhkCiAgICAgICAgVmVyRVJ2cExUaGRhUm1aZ2k3bHkrRHZrWTdMcXlKUHZkSGNxeGVkZ0ZuUEtSNFQrZ1NRbWJVUGQ5cXFkSlIwUQogICAgICAgIEtsL1BtdHVTL3c5Z3kyWjRheTBRSUtyTkJ6UXhoQThMRFpwcDFydWZDSjUrWk1lZjkwdkhwd3hNK09hUHJ5TmwKICAgICAgICBFZERXN1lROGZ1QjVuUHFqd1VBcG1sWVlMSllsZDd2Sjc5RUl4L3NqZ2g2RytJRmltN3hSN1dpUUYvbkpldmZxCiAgICAgICAgdnpZTzdvci9HSUNiNmVad3ZQZHR5NzlIbVZlUHFFVGxEVTAwb3lvcFd5VHNZeVNZRFNIbi80ZG9UdXg4ditGLwogICAgICAgIFlleWJ2Z3FicmlIN2lTRjhIeHdFRmVEanJNdFVUSHNYQzM1REhGZU1DaEpveHN5S3Y0OEorYklHRndBUkFRQUIKICAgICAgICB0QzFKYm1aeVlVaHZkWE5sSUZCaFkydGhaMlZ5SUR4d1lXTnJZV2RsY2tCcGJtWnlZV2h2ZFhObExtTnZiVDZKCiAgICAgICAgQWxRRUV3RUtBRDRXSVFTaU5oNWtZM3c4VzBnQUY4WGd1SmFveGZjRDd3VUNaTHNXMlFJYkF3VUpBOEpuQUFVTAogICAgICAgIENRZ0hBZ1lWQ2drSUN3SUVGZ0lEQVFJZUFRSVhnQUFLQ1JEZ3VKYW94ZmNEN3diN0QvOWVuYnRPMURFUW4xUHQKICAgICAgICBoZ2t0SCtJcmJCZFlSSGs3MWlsMmhibm1BYm9Ma2sxYWsvYWFRWS9YUURKRmhyQTdqTWtQTE9DUmVvdEhpUW12CiAgICAgICAgMVVmcURjTTJlUTQveDBOOUYyRExVU2t1d3cxMTd2dHRVb0J4aXJCNzJwTzBUL2xkOW8zOVNITUMvRGZrNnk2aAogICAgICAgIHRUR3F4TGdoOGozRFN5TzVFRXJKTGEvM0J2TXFyNGlxYjNQVHdOZURSRWphdlFKaFhTdkVGanlBQ29vOWQ3cnMKICAgICAgICA3bGhDYmJTUGpnVGNHL1BDZnpMcjM3UXl6WGlUUi9Ud2ppd1ZkVGhkQ1MvQ0tuc29NOG5nSHhqWFlwSzdNNndnCiAgICAgICAgdHpBOEprSFpyNU1wa3JQR3JnUWV2aEpCTGtIUi9qY3NhYUJaTjdudzhhZUhjd3dNNC9DaEhJeVpkUTkxMDU5cAogICAgICAgIE9NYVltV21qUFFmcTFyT25BQXZBMXhXdytUWk56SGdXSXE0dnVzeDdPQnZyRnNWZVpOc3FkN09hNHBydFZXZzAKICAgICAgICA5MWNLWkpvL092Nm9wTS93RFdOMnlCbmttQkN3YVhwb0g1TkRRMjJiaG5HVEplSVdkZWk4VVNHcHZCa1R4QkkyCiAgICAgICAgWDMycHlPbVpEbjgxTDJ6TTJpb052Z1hJYjV1NXRqYjlOT2lBdDZvVzBHMHgwMGRncjNyNnB1OHFtTXdrQlZCQwogICAgICAgIHZXd0VtYXhRbmtUaG5iQWQ1N1ZiYXQ0Ly91RGNIRnBEYUJQcEZXZUNMMmRmRFNyUzlpaUs2SzFWa3ZHTG9YaDgKICAgICAgICBNcEpxam9kZHBmTmg0dXlmekt5TkUxZHJRMjltY3dmSWx6WG9QcmIwOVc2WkhwbSt0cWQ4TWs3MDd6d3NkRkdSCiAgICAgICAgcVJzeG10UG45SjFyZVlaaVZ1RTVHMjZmMWFLVFI3a0NEUVJrdXhiWkFSQUE0KzlrbjRzbUJYWmNNMHZGcTlSOAogICAgICAgIDI0WEtadFRhVm1Wb1ZKTVJRTTQ0cVdSK3MvUzBNenZiTzV1MGNTVlRoWTY1WXpNTHM5MjBVWTZ1R3BvUzJaWXcKICAgICAgICBJTWlwa2FCKzJGNkI4UjdWN25sL1NnYVhHYTJNZXhrQzd3dDZibEZiYXc3cGJ2SStpSTl3UzhCS0hnTUR6ZDBGCiAgICAgICAgVGpTcTl2ZGtWa2Y3eUkzaEV3bGxYN3pUNklMT3Zrbk5HYm9zMGRGSTkyY0JXUXMraVhQNTB4RFZpdDMrOW1DRAogICAgICAgIHJ1V1ZZazczbXZTRXpGY3VYQ3liS0o1VS9uelNRNzBKb1FtU1BjNTBSUWp1SEdkemwvWXpHRmFGbjV6SVo1cFAKICAgICAgICBrNVMrS1RZZWt6Y2lSa0h6YmVhNVBqK0E2S1ppbEtqNXlrQVJGencrQ1B4cXN1ZWpEa2k3QSthM20zV0dxK21tCiAgICAgICAgQWtsUTRZQmNvbHpOT3BnV2NsSVN1RTNkNWtndGFKQUNJZ3RlODdGNlFCQnNrOG9EQkZRQ25abW9PaXJsU2xiZgogICAgICAgIEp1RDZmVkNKdTJ6WTdUaE4xTzBvV1R3QWFOQXZNNTVDTFR2NnMzRm10UjkybG5sUURGdUorZmo4NjNjNnF4MTQKICAgICAgICBGdU80bU03ZXVTMDh3R2dWR205MXdBN2JZbDRhaHhDNlMyQkdCNUZ2a1pmekJCd2pzZm1VV0hBdTdWUlpKeGtYCiAgICAgICAgSnA2OTZPVGRSM1JmSTdJWjZPVzZ0R0VMaWpzd1diYlpYYjVYUldFVzk5dldPN05JSzZzT3ZoTUROcDliU011YgogICAgICAgIFhQM1BiUHhneVQwYm1zczB5d05Zd3VjbmZjbURYcVBWdTNHZHQ1M2F0MStoSzdtbG5RM3VVczVlVkVPSUhuSm0KICAgICAgICBmMXRyRGdnU1RFN2Zua3g2Q3psK2lNa0FFUUVBQVlrQ1BBUVlBUW9BSmhZaEJLSTJIbVJqZkR4YlNBQVh4ZUM0CiAgICAgICAgbHFqRjl3UHZCUUprdXhiWkFoc01CUWtEd21jQUFBb0pFT0M0bHFqRjl3UHY4U1FQL2pzUWZKQ1VIcmpwWDRmUAogICAgICAgIDBOdFZ5cWxDcnExT21MUDdCTHJYckN4b0FGUmI2NFlKVWRXazVQMzVrOXdqMkJRanBqY05qMmlrODBGb28wMkUKICAgICAgICB5YytQelcvNHR6VnZkeFJyRXpzT0ZtK21NUitsbFVIQUt6QmE2UUJ4SFQwb2ZMN3A1WFlUdU1ObllvK1BqVk1tCiAgICAgICAgalAzVEVKR1lYWW11aEdmYWFKWnBqTG1KRnFwNTl4Ly9kc01IZUxxVUNod2I2Q2c2RHVrQWloZUFzM1ArclhvMwogICAgICAgIHRCbkE0SkNDaVhSNy8vMFdlelJvU1BkYWxOZW00dnM4UFQ4N3NuSGJEbGlGTVZmOHcrZmtzSW5xdm90aVJESTQKICAgICAgICBRQnJCZnMzTmRlWlcvdG11cE9hWkpSekhEdnZLYmcvL082aXAxYVB2SUxXdlRETThLY1FDUUVTYVdrQ2JJMXVjCiAgICAgICAgcml6QU1ibFRCMmd5dzl5b2pDcFZDTUJYZGl6QXFxeWw1WlZydzQrWC9pMDlJc050OGhBOS81Ulk3djNjN1oyQwogICAgICAgIFh5MnhLV210TEk5bmxPU1N3VXhCNTY2STI5bFZLQkxVbVhtUWZuUklJSENpSkRYWUZEUC82TGZ2OSttaEVXVTgKICAgICAgICBxZWQzeGhwZU5TQUl6QStNVGxqdGlSbW9yeHBkZGlYYnRDYWZjUGwvSjNYMEIwN2ZjY0pad1pzQ1lDcHRMeTFjCiAgICAgICAgeXZWYU4rRUJtam9DcDNqdDZ3TGU0eGNscVUzQUN3ei84VEREbXRKN1VVZGw3TWRraXBRWjI3OEwya3BsNm82MQogICAgICAgIE1GMmZYRDdmWk1lWmZFdzZsdTBCRjVtWjAvY2gzSHhYZVpvWGlmNzlnMjV2Wm1TZFc5N3BjZWV3UGx2bEVURlEKICAgICAgICA1NXBNb3JReVVURVFDUTNFQ3pIWVNuTC9UbVc3CiAgICAgICAgPSswUmMKICAgICAgICAtLS0tLUVORCBQR1AgUFVCTElDIEtFWSBCTE9DSy0tLS0tCiAgICAgICJzb3VyY2UiOiAiZGViIFtzaWduZWQtYnk9JEtFWV9GSUxFXSBodHRwczovL3JlbGVhc2UtamFtbXkuaW5mcmFob3VzZS5jb20vICRSRUxFQVNFCiAgICAgICAgbWFpbiIKInBhY2thZ2VfdXBkYXRlIjogdHJ1ZQoicGFja2FnZXMiOgotICJtYWtlIgotICJnY2MiCi0gInB1cHBldC1jb2RlIgotICJpbmZyYWhvdXNlLXRvb2xraXQiCi0gImluZnJhaG91c2UtcHVwcGV0LWRhdGEiCiJwdXBwZXQiOgogICJjb2xsZWN0aW9uIjogInB1cHBldDgiCiAgImluc3RhbGwiOiB0cnVlCiAgImluc3RhbGxfdHlwZSI6ICJhaW8iCiAgInBhY2thZ2VfbmFtZSI6ICJwdXBwZXQtYWdlbnQiCiAgInN0YXJ0X3NlcnZpY2UiOiBmYWxzZQoicnVuY21kIjoKLSAiL29wdC9wdXBwZXRsYWJzL3B1cHBldC9iaW4vZ2VtIGluc3RhbGwganNvbiIKLSAiL29wdC9wdXBwZXRsYWJzL3B1cHBldC9iaW4vZ2VtIGluc3RhbGwgYXdzLXNkay1jb3JlIgotICIvb3B0L3B1cHBldGxhYnMvcHVwcGV0L2Jpbi9nZW0gaW5zdGFsbCBhd3Mtc2RrLXNlY3JldHNtYW5hZ2VyIgotICJpaC1wdXBwZXQgIC0tZW52aXJvbm1lbnQgcHJvZHVjdGlvbiAtLWVudmlyb25tZW50cGF0aCB7cm9vdF9kaXJlY3Rvcnl9L2Vudmlyb25tZW50cwogIC0tcm9vdC1kaXJlY3RvcnkgL29wdC9wdXBwZXQtY29kZSAtLWhpZXJhLWNvbmZpZyAvb3B0L2luZnJhaG91c2UtcHVwcGV0LWRhdGEvZW52aXJvbm1lbnRzL3Byb2R1Y3Rpb24vaGllcmEueWFtbAogIC0tbW9kdWxlLXBhdGgge3Jvb3RfZGlyZWN0b3J5fS9tb2R1bGVzIGFwcGx5IC9vcHQvcHVwcGV0LWNvZGUvZW52aXJvbm1lbnRzL3Byb2R1Y3Rpb24vbWFuaWZlc3RzL3NpdGUucHAiCiJ3cml0ZV9maWxlcyI6Ci0gImNvbnRlbnQiOiAiZXhwb3J0IEFXU19ERUZBVUxUX1JFR0lPTj11cy13ZXN0LTEiCiAgInBhdGgiOiAiL2V0Yy9wcm9maWxlLmQvYXdzLnNoIgogICJwZXJtaXNzaW9ucyI6ICIwNjQ0IgotICJjb250ZW50IjogfC0KICAgIFtkZWZhdWx0XQogICAgcmVnaW9uPXVzLXdlc3QtMQogICJwYXRoIjogIi9yb290Ly5hd3MvY29uZmlnIgogICJwZXJtaXNzaW9ucyI6ICIwNjAwIgotICJjb250ZW50IjogfAogICAgInB1cHBldF9lbnZpcm9ubWVudCI6ICJwcm9kdWN0aW9uIgogICAgInB1cHBldF9yb2xlIjogIndlYnNlcnZlciIKICAicGF0aCI6ICIvZXRjL3B1cHBldGxhYnMvZmFjdGVyL2ZhY3RzLmQvcHVwcGV0LnlhbWwiCiAgInBlcm1pc3Npb25zIjogIjA2NDQiCi0gImNvbnRlbnQiOiAie1wiaWgtcHVwcGV0XCI6e1wiZGVidWdcIjpmYWxzZSxcImVudmlyb25tZW50cGF0aFwiOlwie3Jvb3RfZGlyZWN0b3J5fS9lbnZpcm9ubWVudHNcIixcImhpZXJhLWNvbmZpZ1wiOlwiL29wdC9pbmZyYWhvdXNlLXB1cHBldC1kYXRhL2Vudmlyb25tZW50cy9wcm9kdWN0aW9uL2hpZXJhLnlhbWxcIixcIm1hbmlmZXN0XCI6XCIvb3B0L3B1cHBldC1jb2RlL2Vudmlyb25tZW50cy9wcm9kdWN0aW9uL21hbmlmZXN0cy9zaXRlLnBwXCIsXCJtb2R1bGUtcGF0aFwiOlwie3Jvb3RfZGlyZWN0b3J5fS9tb2R1bGVzXCIsXCJyb290LWRpcmVjdG9yeVwiOlwiL29wdC9wdXBwZXQtY29kZVwifX0iCiAgInBhdGgiOiAiL2V0Yy9wdXBwZXRsYWJzL2ZhY3Rlci9mYWN0cy5kL2loLXB1cHBldC5qc29uIgogICJwZXJtaXNzaW9ucyI6ICIwNjQ0IgotICJjb250ZW50IjogInt9IgogICJwYXRoIjogIi9ldGMvcHVwcGV0bGFicy9mYWN0ZXIvZmFjdHMuZC9jdXN0b20uanNvbiIKICAicGVybWlzc2lvbnMiOiAiMDY0NCIKDQotLU1JTUVCT1VOREFSWS0tDQo=" -> "Q29udGVudC1UeXBlOiBtdWx0aXBhcnQvbWl4ZWQ7IGJvdW5kYXJ5PSJNSU1FQk9VTkRBUlkiCk1JTUUtVmVyc2lvbjogMS4wDQoNCi0tTUlNRUJPVU5EQVJZDQpDb250ZW50LVRyYW5zZmVyLUVuY29kaW5nOiA3Yml0DQpDb250ZW50LVR5cGU6IHRleHQvY2xvdWQtY29uZmlnDQpNaW1lLVZlcnNpb246IDEuMA0KDQojY2xvdWQtY29uZmlnCiJhcHQiOgogICJzb3VyY2VzIjoKICAgICJpbmZyYWhvdXNlIjoKICAgICAgImtleSI6IHwKICAgICAgICAtLS0tLUJFR0lOIFBHUCBQVUJMSUMgS0VZIEJMT0NLLS0tLS0KCiAgICAgICAgbVFJTkJHUzdGdGtCRUFERitZbURnNlF2c3Y1VjZaUXcrUWh4ZFR2ak1YZUxDOVQ2UkZSVkQ5NDdxS3p0Tk5RbgogICAgICAgICtBL3l4cHJMQW1XMjVVdS8xMW9Dc3pOVklJYVIzT1k4TXR5aWxiQ3R6VWtCenZXZGxYM0h2VHc5MUxwOGJ4VUwKICAgICAgICBFWE9NOW5zY3FPck92ZkJqYW5wbEtERUtQTVk2dklaM2twMXJVc0NOR0xCTDB4MktaZ1U4MHVsUnNNTThxbkJOCiAgICAgICAga3BUaUFlWEtPRVZ0UnpsV2x2T0ZMSjdwWUR2YVowVWdIU1Z1RStaa2xkcU9kTExScEtrZEl2SlBja1hxTDV4VAogICAgICAgIFV2V1RXMWVuRkFIZDUrTlF4TW5DYTNpa2pRVjNEVGxFanNnTExRYmJ5c1hqWFByNlBJUHMyOWNUY2ZvcTQzMU8KICAgICAgICB0UjREclpCNHZNRU9BODhUbUtCa0VpTUcraUI5Y2p6NXdCSXVNdTk1Wm1vSnhkdmpQUjcyRllLZ3JDWE50TmhkCiAgICAgICAgVmVyRVJ2cExUaGRhUm1aZ2k3bHkrRHZrWTdMcXlKUHZkSGNxeGVkZ0ZuUEtSNFQrZ1NRbWJVUGQ5cXFkSlIwUQogICAgICAgIEtsL1BtdHVTL3c5Z3kyWjRheTBRSUtyTkJ6UXhoQThMRFpwcDFydWZDSjUrWk1lZjkwdkhwd3hNK09hUHJ5TmwKICAgICAgICBFZERXN1lROGZ1QjVuUHFqd1VBcG1sWVlMSllsZDd2Sjc5RUl4L3NqZ2g2RytJRmltN3hSN1dpUUYvbkpldmZxCiAgICAgICAgdnpZTzdvci9HSUNiNmVad3ZQZHR5NzlIbVZlUHFFVGxEVTAwb3lvcFd5VHNZeVNZRFNIbi80ZG9UdXg4ditGLwogICAgICAgIFlleWJ2Z3FicmlIN2lTRjhIeHdFRmVEanJNdFVUSHNYQzM1REhGZU1DaEpveHN5S3Y0OEorYklHRndBUkFRQUIKICAgICAgICB0QzFKYm1aeVlVaHZkWE5sSUZCaFkydGhaMlZ5SUR4d1lXTnJZV2RsY2tCcGJtWnlZV2h2ZFhObExtTnZiVDZKCiAgICAgICAgQWxRRUV3RUtBRDRXSVFTaU5oNWtZM3c4VzBnQUY4WGd1SmFveGZjRDd3VUNaTHNXMlFJYkF3VUpBOEpuQUFVTAogICAgICAgIENRZ0hBZ1lWQ2drSUN3SUVGZ0lEQVFJZUFRSVhnQUFLQ1JEZ3VKYW94ZmNEN3diN0QvOWVuYnRPMURFUW4xUHQKICAgICAgICBoZ2t0SCtJcmJCZFlSSGs3MWlsMmhibm1BYm9Ma2sxYWsvYWFRWS9YUURKRmhyQTdqTWtQTE9DUmVvdEhpUW12CiAgICAgICAgMVVmcURjTTJlUTQveDBOOUYyRExVU2t1d3cxMTd2dHRVb0J4aXJCNzJwTzBUL2xkOW8zOVNITUMvRGZrNnk2aAogICAgICAgIHRUR3F4TGdoOGozRFN5TzVFRXJKTGEvM0J2TXFyNGlxYjNQVHdOZURSRWphdlFKaFhTdkVGanlBQ29vOWQ3cnMKICAgICAgICA3bGhDYmJTUGpnVGNHL1BDZnpMcjM3UXl6WGlUUi9Ud2ppd1ZkVGhkQ1MvQ0tuc29NOG5nSHhqWFlwSzdNNndnCiAgICAgICAgdHpBOEprSFpyNU1wa3JQR3JnUWV2aEpCTGtIUi9qY3NhYUJaTjdudzhhZUhjd3dNNC9DaEhJeVpkUTkxMDU5cAogICAgICAgIE9NYVltV21qUFFmcTFyT25BQXZBMXhXdytUWk56SGdXSXE0dnVzeDdPQnZyRnNWZVpOc3FkN09hNHBydFZXZzAKICAgICAgICA5MWNLWkpvL092Nm9wTS93RFdOMnlCbmttQkN3YVhwb0g1TkRRMjJiaG5HVEplSVdkZWk4VVNHcHZCa1R4QkkyCiAgICAgICAgWDMycHlPbVpEbjgxTDJ6TTJpb052Z1hJYjV1NXRqYjlOT2lBdDZvVzBHMHgwMGRncjNyNnB1OHFtTXdrQlZCQwogICAgICAgIHZXd0VtYXhRbmtUaG5iQWQ1N1ZiYXQ0Ly91RGNIRnBEYUJQcEZXZUNMMmRmRFNyUzlpaUs2SzFWa3ZHTG9YaDgKICAgICAgICBNcEpxam9kZHBmTmg0dXlmekt5TkUxZHJRMjltY3dmSWx6WG9QcmIwOVc2WkhwbSt0cWQ4TWs3MDd6d3NkRkdSCiAgICAgICAgcVJzeG10UG45SjFyZVlaaVZ1RTVHMjZmMWFLVFI3a0NEUVJrdXhiWkFSQUE0KzlrbjRzbUJYWmNNMHZGcTlSOAogICAgICAgIDI0WEtadFRhVm1Wb1ZKTVJRTTQ0cVdSK3MvUzBNenZiTzV1MGNTVlRoWTY1WXpNTHM5MjBVWTZ1R3BvUzJaWXcKICAgICAgICBJTWlwa2FCKzJGNkI4UjdWN25sL1NnYVhHYTJNZXhrQzd3dDZibEZiYXc3cGJ2SStpSTl3UzhCS0hnTUR6ZDBGCiAgICAgICAgVGpTcTl2ZGtWa2Y3eUkzaEV3bGxYN3pUNklMT3Zrbk5HYm9zMGRGSTkyY0JXUXMraVhQNTB4RFZpdDMrOW1DRAogICAgICAgIHJ1V1ZZazczbXZTRXpGY3VYQ3liS0o1VS9uelNRNzBKb1FtU1BjNTBSUWp1SEdkemwvWXpHRmFGbjV6SVo1cFAKICAgICAgICBrNVMrS1RZZWt6Y2lSa0h6YmVhNVBqK0E2S1ppbEtqNXlrQVJGencrQ1B4cXN1ZWpEa2k3QSthM20zV0dxK21tCiAgICAgICAgQWtsUTRZQmNvbHpOT3BnV2NsSVN1RTNkNWtndGFKQUNJZ3RlODdGNlFCQnNrOG9EQkZRQ25abW9PaXJsU2xiZgogICAgICAgIEp1RDZmVkNKdTJ6WTdUaE4xTzBvV1R3QWFOQXZNNTVDTFR2NnMzRm10UjkybG5sUURGdUorZmo4NjNjNnF4MTQKICAgICAgICBGdU80bU03ZXVTMDh3R2dWR205MXdBN2JZbDRhaHhDNlMyQkdCNUZ2a1pmekJCd2pzZm1VV0hBdTdWUlpKeGtYCiAgICAgICAgSnA2OTZPVGRSM1JmSTdJWjZPVzZ0R0VMaWpzd1diYlpYYjVYUldFVzk5dldPN05JSzZzT3ZoTUROcDliU011YgogICAgICAgIFhQM1BiUHhneVQwYm1zczB5d05Zd3VjbmZjbURYcVBWdTNHZHQ1M2F0MStoSzdtbG5RM3VVczVlVkVPSUhuSm0KICAgICAgICBmMXRyRGdnU1RFN2Zua3g2Q3psK2lNa0FFUUVBQVlrQ1BBUVlBUW9BSmhZaEJLSTJIbVJqZkR4YlNBQVh4ZUM0CiAgICAgICAgbHFqRjl3UHZCUUprdXhiWkFoc01CUWtEd21jQUFBb0pFT0M0bHFqRjl3UHY4U1FQL2pzUWZKQ1VIcmpwWDRmUAogICAgICAgIDBOdFZ5cWxDcnExT21MUDdCTHJYckN4b0FGUmI2NFlKVWRXazVQMzVrOXdqMkJRanBqY05qMmlrODBGb28wMkUKICAgICAgICB5YytQelcvNHR6VnZkeFJyRXpzT0ZtK21NUitsbFVIQUt6QmE2UUJ4SFQwb2ZMN3A1WFlUdU1ObllvK1BqVk1tCiAgICAgICAgalAzVEVKR1lYWW11aEdmYWFKWnBqTG1KRnFwNTl4Ly9kc01IZUxxVUNod2I2Q2c2RHVrQWloZUFzM1ArclhvMwogICAgICAgIHRCbkE0SkNDaVhSNy8vMFdlelJvU1BkYWxOZW00dnM4UFQ4N3NuSGJEbGlGTVZmOHcrZmtzSW5xdm90aVJESTQKICAgICAgICBRQnJCZnMzTmRlWlcvdG11cE9hWkpSekhEdnZLYmcvL082aXAxYVB2SUxXdlRETThLY1FDUUVTYVdrQ2JJMXVjCiAgICAgICAgcml6QU1ibFRCMmd5dzl5b2pDcFZDTUJYZGl6QXFxeWw1WlZydzQrWC9pMDlJc050OGhBOS81Ulk3djNjN1oyQwogICAgICAgIFh5MnhLV210TEk5bmxPU1N3VXhCNTY2STI5bFZLQkxVbVhtUWZuUklJSENpSkRYWUZEUC82TGZ2OSttaEVXVTgKICAgICAgICBxZWQzeGhwZU5TQUl6QStNVGxqdGlSbW9yeHBkZGlYYnRDYWZjUGwvSjNYMEIwN2ZjY0pad1pzQ1lDcHRMeTFjCiAgICAgICAgeXZWYU4rRUJtam9DcDNqdDZ3TGU0eGNscVUzQUN3ei84VEREbXRKN1VVZGw3TWRraXBRWjI3OEwya3BsNm82MQogICAgICAgIE1GMmZYRDdmWk1lWmZFdzZsdTBCRjVtWjAvY2gzSHhYZVpvWGlmNzlnMjV2Wm1TZFc5N3BjZWV3UGx2bEVURlEKICAgICAgICA1NXBNb3JReVVURVFDUTNFQ3pIWVNuTC9UbVc3CiAgICAgICAgPSswUmMKICAgICAgICAtLS0tLUVORCBQR1AgUFVCTElDIEtFWSBCTE9DSy0tLS0tCiAgICAgICJzb3VyY2UiOiAiZGViIFtzaWduZWQtYnk9JEtFWV9GSUxFXSBodHRwczovL3JlbGVhc2UtamFtbXkuaW5mcmFob3VzZS5jb20vICRSRUxFQVNFCiAgICAgICAgbWFpbiIKInBhY2thZ2VfdXBkYXRlIjogdHJ1ZQoicGFja2FnZXMiOgotICJtYWtlIgotICJnY2MiCi0gInB1cHBldC1jb2RlIgotICJpbmZyYWhvdXNlLXRvb2xraXQiCi0gImluZnJhaG91c2UtcHVwcGV0LWRhdGEiCiJwdXBwZXQiOgogICJjb2xsZWN0aW9uIjogInB1cHBldDgiCiAgImluc3RhbGwiOiB0cnVlCiAgImluc3RhbGxfdHlwZSI6ICJhaW8iCiAgInBhY2thZ2VfbmFtZSI6ICJwdXBwZXQtYWdlbnQiCiAgInN0YXJ0X3NlcnZpY2UiOiBmYWxzZQoicnVuY21kIjoKLSAiL29wdC9wdXBwZXRsYWJzL3B1cHBldC9iaW4vZ2VtIGluc3RhbGwganNvbiIKLSAiL29wdC9wdXBwZXRsYWJzL3B1cHBldC9iaW4vZ2VtIGluc3RhbGwgYXdzLXNkay1jb3JlIgotICIvb3B0L3B1cHBldGxhYnMvcHVwcGV0L2Jpbi9nZW0gaW5zdGFsbCBhd3Mtc2RrLXNlY3JldHNtYW5hZ2VyIgotICJpaC1wdXBwZXQgIC0tZW52aXJvbm1lbnQgcHJvZHVjdGlvbiAtLWVudmlyb25tZW50cGF0aCB7cm9vdF9kaXJlY3Rvcnl9L2Vudmlyb25tZW50cwogIC0tcm9vdC1kaXJlY3RvcnkgL29wdC9wdXBwZXQtY29kZSAtLWhpZXJhLWNvbmZpZyAvb3B0L2luZnJhaG91c2UtcHVwcGV0LWRhdGEvZW52aXJvbm1lbnRzL3Byb2R1Y3Rpb24vaGllcmEueWFtbAogIC0tbW9kdWxlLXBhdGgge3Jvb3RfZGlyZWN0b3J5fS9tb2R1bGVzIGFwcGx5IC9vcHQvcHVwcGV0LWNvZGUvZW52aXJvbm1lbnRzL3Byb2R1Y3Rpb24vbWFuaWZlc3RzL3NpdGUucHAiCiJ3cml0ZV9maWxlcyI6Ci0gImNvbnRlbnQiOiAiZXhwb3J0IEFXU19ERUZBVUxUX1JFR0lPTj11cy13ZXN0LTEiCiAgInBhdGgiOiAiL2V0Yy9wcm9maWxlLmQvYXdzLnNoIgogICJwZXJtaXNzaW9ucyI6ICIwNjQ0IgotICJjb250ZW50IjogfC0KICAgIFtkZWZhdWx0XQogICAgcmVnaW9uPXVzLXdlc3QtMQogICJwYXRoIjogIi9yb290Ly5hd3MvY29uZmlnIgogICJwZXJtaXNzaW9ucyI6ICIwNjAwIgotICJjb250ZW50IjogfAogICAgInB1cHBldF9lbnZpcm9ubWVudCI6ICJwcm9kdWN0aW9uIgogICAgInB1cHBldF9yb2xlIjogIndlYnNlcnZlciIKICAicGF0aCI6ICIvZXRjL3B1cHBldGxhYnMvZmFjdGVyL2ZhY3RzLmQvcHVwcGV0LnlhbWwiCiAgInBlcm1pc3Npb25zIjogIjA2NDQiCi0gImNvbnRlbnQiOiAie1wiaWgtcHVwcGV0XCI6e1wiY2FuY2VsX2luc3RhbmNlX3JlZnJlc2hfb25fZXJyb3JcIjpmYWxzZSxcImRlYnVnXCI6ZmFsc2UsXCJlbnZpcm9ubWVudHBhdGhcIjpcIntyb290X2RpcmVjdG9yeX0vZW52aXJvbm1lbnRzXCIsXCJoaWVyYS1jb25maWdcIjpcIi9vcHQvaW5mcmFob3VzZS1wdXBwZXQtZGF0YS9lbnZpcm9ubWVudHMvcHJvZHVjdGlvbi9oaWVyYS55YW1sXCIsXCJtYW5pZmVzdFwiOlwiL29wdC9wdXBwZXQtY29kZS9lbnZpcm9ubWVudHMvcHJvZHVjdGlvbi9tYW5pZmVzdHMvc2l0ZS5wcFwiLFwibW9kdWxlLXBhdGhcIjpcIntyb290X2RpcmVjdG9yeX0vbW9kdWxlc1wiLFwicm9vdC1kaXJlY3RvcnlcIjpcIi9vcHQvcHVwcGV0LWNvZGVcIn19IgogICJwYXRoIjogIi9ldGMvcHVwcGV0bGFicy9mYWN0ZXIvZmFjdHMuZC9paC1wdXBwZXQuanNvbiIKICAicGVybWlzc2lvbnMiOiAiMDY0NCIKLSAiY29udGVudCI6ICJ7fSIKICAicGF0aCI6ICIvZXRjL3B1cHBldGxhYnMvZmFjdGVyL2ZhY3RzLmQvY3VzdG9tLmpzb24iCiAgInBlcm1pc3Npb25zIjogIjA2NDQiCg0KLS1NSU1FQk9VTkRBUlktLQ0K"
userdata changes:
--- before
+++ after
@@ -99,7 +99,7 @@
     "puppet_role": "webserver"
   "path": "/etc/puppetlabs/facter/facts.d/puppet.yaml"
   "permissions": "0644"
-- "content": "{\\"ih-puppet\\":{\\"debug\\":false,\\"environmentpath\\":\\"{root_directory}/environments\\",\\"hiera-config\\":\\"/opt/infrahouse-puppet-data/environments/production/hiera.yaml\\",\\"manifest\\":\\"/opt/puppet-code/environments/production/manifests/site.pp\\",\\"module-path\\":\\"{root_directory}/modules\\",\\"root-directory\\":\\"/opt/puppet-code\\"}}"
+- "content": "{\\"ih-puppet\\":{\\"cancel_instance_refresh_on_error\\":false,\\"debug\\":false,\\"environmentpath\\":\\"{root_directory}/environments\\",\\"hiera-config\\":\\"/opt/infrahouse-puppet-data/environments/production/hiera.yaml\\",\\"manifest\\":\\"/opt/puppet-code/environments/production/manifests/site.pp\\",\\"module-path\\":\\"{root_directory}/modules\\",\\"root-directory\\":\\"/opt/puppet-code\\"}}"
   "path": "/etc/puppetlabs/facter/facts.d/ih-puppet.json"
   "permissions": "0644"
 - "content": "{}"
EOF userdata changes.
        # (16 unchanged attributes hidden)

      + metadata_options {
          + http_tokens = "required"
        }

        # (4 unchanged blocks hidden)
    }

Plan: 0 to add, 2 to change, 0 to destroy.

─────────────────────────────────────────────────────────────────────────────

Saved the plan to: tf.plan

To perform exactly these actions, run the following command to apply:
    terraform apply "tf.plan"
```
</details>
<details><summary><i>metadata</i></summary>

```
eyJzMzovL2Zvb19iYWNrZXQvcGF0aC90by90Zi5zdGF0ZSI6IHsic3VjY2VzcyI6IHRydWUsICJhZGQiOiAwLCAiY2hhbmdlIjogMiwgImRlc3Ryb3kiOiAwfX0=
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
