from infrahouse_toolkit.terraform.backends.s3backend import TFS3Backend


def test_eq():
    assert TFS3Backend("foobucket", "foo.key") == TFS3Backend("foobucket", "foo.key")
    assert TFS3Backend("foobucket", "foo.key") != TFS3Backend("barbucket", "foo.key")
