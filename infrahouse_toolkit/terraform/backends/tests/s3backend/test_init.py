from infrahouse_toolkit.terraform.backends.s3backend import TFS3Backend


def test_init():
    assert TFS3Backend("foobucket", "foo.key")
