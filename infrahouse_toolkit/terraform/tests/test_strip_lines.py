from textwrap import dedent

import pytest

from infrahouse_toolkit.terraform.status import strip_lines


@pytest.mark.parametrize(
    "in_text, pattern, out_text",
    [
        ("foo", "bar", "foo"),
        ("", "bar", ""),
        (
            dedent(
                """
                test line 1
                test line 2
                test line 3
                ::debug::Terraform exited with code 0.
                ::debug::stdout: module.jumphost
                ::debug::stderr:
                ::debug::exitcode: 0
                """
            ),
            "::debug::",
            dedent(
                """
                test line 1
                test line 2
                test line 3
                """
            ),
        ),
    ],
)
def test_strip_lines(in_text, pattern, out_text):
    assert strip_lines(in_text, pattern) == out_text
