from infrahouse_toolkit.cli.ih_plan.cmd_min_permissions import ActionList


def test_add_sorted():
    """Ensure sorted order"""
    actions1 = ActionList()
    actions1.add("foo")
    actions1.add("bar")

    actions2 = ActionList()
    actions2.add("bar")
    actions2.add("foo")

    assert actions1.actions == actions2.actions


def test_add():
    """add() an action and maintain uniqueness."""
    actions = ActionList()
    actions.add("foo")
    assert actions.actions == ["foo"]

    actions.add("foo")
    assert actions.actions == ["foo"]

    actions.add("bar")
    assert "bar" in actions.actions
    assert "foo" in actions.actions


def test_add_with_dependency():
    actions = ActionList()
    actions.add("autoscaling:CreateAutoScalingGroup")

    assert "autoscaling:CreateAutoScalingGroup" in actions.actions
    assert "iam:PassRole" in actions.actions
    assert "iam:CreateServiceLinkedRole" in actions.actions


def test_add_with_rewrite():
    actions = ActionList()
    actions.add("auto scaling:foo")

    assert actions.actions == ["autoscaling:foo"]
