from infrahouse_toolkit.cli.ih_plan.cmd_min_permissions import ActionList


def test_actions():
    assert ActionList().actions == []
