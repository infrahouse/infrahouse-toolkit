"""Fixtures."""

from textwrap import dedent

import pytest


@pytest.fixture
def terraform_tf(tmp_path):
    """
    Return a temporary path with a Terraform backend configuration.

    :param tmp_path: pytest's tmp_path fixture.
    :type tmp_path: pathlib.Path
    :return: A temporary file with the Terraform backend configuration.
    """
    tf_backend = tmp_path / "terraform.tf"
    tf_backend.write_text(
        dedent(
            """
            terraform {
              backend "s3" {
                bucket = "infrahouse-foo"
                key    = "github.state"
              }
              required_providers {}
            }
            """
        )
    )
    return tf_backend
