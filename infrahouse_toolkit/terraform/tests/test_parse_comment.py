import pytest

from infrahouse_toolkit.terraform import RunResult, TFStatus, parse_comment
from infrahouse_toolkit.terraform.backends import TFS3Backend
from infrahouse_toolkit.terraform.exceptions import IHParseError
from infrahouse_toolkit.terraform.status import RunOutput


@pytest.mark.parametrize("comment_text", ["", None, "foo"])
def test_parse_comment_raises(comment_text):
    with pytest.raises(IHParseError):
        parse_comment(comment_text)


@pytest.mark.parametrize(
    "comment_text, status",
    [
        (
            TFStatus(
                TFS3Backend("foo_backet", "path/to/tf.state"),
                success=True,
                run_result=RunResult(1, 1, 1),
                run_output=RunOutput("no stdout", None),
            ).comment,
            TFStatus(
                TFS3Backend("foo_backet", "path/to/tf.state"),
                success=True,
                run_result=RunResult(1, 1, 1),
                run_output=RunOutput("no stdout", None),
            ),
        ),
        (
            TFStatus(
                TFS3Backend("foo_backet", "path/to/tf.state"),
                success=True,
                run_result=RunResult(1, 1, 1),
                run_output=RunOutput(None, None),
            ).comment,
            TFStatus(
                TFS3Backend("foo_backet", "path/to/tf.state"),
                success=True,
                run_result=RunResult(1, 1, 1),
                run_output=RunOutput(None, None),
            ),
        ),
        # lines are terminated by \r\n
        (
            """# **`s3://foo_backet/path/to/tf.state`**
|  Success  |   🟢 Add |   🟡 Change |   🔴 Destroy |
|:---------:|--------:|-----------:|------------:|
|     ✅     |       1 |          1 |           1 |
<details><summary>STDOUT</summary>

```no stdout```

</details>

<details><summary>STDERR</summary>

```no output```

</details>

<details><summary><i>metadata</i></summary>\r
<p>

```
eyJzMzovL2Zvb19iYWNrZXQvcGF0aC90by90Zi5zdGF0ZSI6IHsic3VjY2VzcyI6IHRydWUsICJzdGRvdXQiOiAibm8gc3Rkb3V0IiwgInN0ZGVyciI6IG51bGwsICJhZGQiOiAxLCAiY2hhbmdlIjogMSwgImRlc3Ryb3kiOiAxfX0=
```

</p>
</details>

    """,
            TFStatus(
                TFS3Backend("foo_backet", "path/to/tf.state"),
                success=True,
                run_result=RunResult(1, 1, 1),
                run_output=RunOutput("no stdout", None),
            ),
        ),
    ],
)
def test_parse_comment(comment_text, status):
    parsed_status = parse_comment(comment_text)
    print(f"\n{parsed_status = }")
    print(f"       {status = }")
    assert parsed_status == status
