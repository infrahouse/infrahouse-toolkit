import json

from infrahouse_toolkit.cli.ih_plan.cmd_min_permissions import ActionList


def test_load_from_file(tmpdir):
    existing = tmpdir.join("existing.json")
    existing.write(json.dumps(["foo", "bar"]))
    actions = ActionList()
    actions.load_from_file(str(existing))
    assert actions.actions == ["bar", "foo"]
