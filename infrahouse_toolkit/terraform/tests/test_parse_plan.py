"""parse_plan() tests."""

# import os.path
from os import path as osp

import pytest

from infrahouse_toolkit.terraform import parse_plan
from infrahouse_toolkit.terraform.status import RunResult

# pylint: disable=line-too-long


@pytest.mark.parametrize(
    "output, expected_result",
    [
        (
            "",
            (RunResult(None, None, None), RunResult(None, None, None)),
        ),
        (None, (RunResult(None, None, None), RunResult(None, None, None))),
        (
            open(osp.join(osp.dirname(osp.realpath(__file__)), "plans/plan-0-0-0.stdout")).read(),
            (
                RunResult(0, 0, 0),
                RunResult(
                    [],
                    [],
                    [],
                ),
            ),
        ),
        (
            open(osp.join(osp.dirname(osp.realpath(__file__)), "plans/plan-2-0-0.stdout")).read(),
            (
                RunResult(2, 0, 0),
                RunResult(
                    [
                        'module.repos["test"].github_repository.repo',
                        'module.repos["test"].github_team_repository.dev',
                    ],
                    [],
                    [],
                ),
            ),
        ),
        (
            open(osp.join(osp.dirname(osp.realpath(__file__)), "plans/plan-2-1-2.stdout")).read(),
            (
                RunResult(2, 1, 2),
                RunResult(
                    [
                        'module.repos["test"].github_repository.repo',
                        'module.repos["test"].github_team_repository.dev',
                    ],
                    ['module.repos["infrahouse-toolkit"].github_repository.repo'],
                    [
                        'module.repos["cookiecutter-github-control"].github_repository.repo',
                        'module.repos["cookiecutter-github-control"].github_team_repository.dev',
                    ],
                ),
            ),
        ),
        (
            open(osp.join(osp.dirname(osp.realpath(__file__)), "plans/plan-3-0-0.stdout")).read(),
            (
                RunResult(3, 0, 0),
                RunResult(
                    [
                        'module.repos["terraform-aws-ci-cd"].github_actions_secret.secret["GH_TOKEN"]',
                        'module.repos["terraform-aws-ci-cd"].github_repository.repo',
                        'module.repos["terraform-aws-ci-cd"].github_team_repository.dev',
                    ],
                    [],
                    [],
                ),
            ),
        ),
    ],
)
def test_parse_plan(output, expected_result):
    """
    parse_plan() returns valid result.

    :param output: terraform plan output.
    :param expected_result: expected result.
    """
    result = parse_plan(output)
    assert result == expected_result
    assert isinstance(result[0], RunResult)
    assert isinstance(result[1], RunResult)
