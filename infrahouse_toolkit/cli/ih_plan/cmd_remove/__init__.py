"""
.. topic:: ``ih-plan remove``

    A ``ih-plan remove`` subcommand.

    See ``ih-plan remove --help`` for more details.
"""

import click

from infrahouse_toolkit.cli.lib import get_bucket, get_s3_client


def validate_key_name(ctx, param, value):  # pylint: disable=unused-argument
    """Check if passed value ends with a ".state"."""
    bad_ending = ".state"
    if value.endswith(bad_ending):
        raise click.BadParameter(f"The file cannot end with a {bad_ending}")

    return value


@click.command(name="remove")
@click.argument("key_name", callback=validate_key_name)
@click.pass_context
def cmd_remove(ctx, key_name):
    """
    Remove a file from an S3 bucket.

    It could be a simple ``aws s3 rm s3://...`` but the command will do two things additionally:

    \b
    - It will parse a Terraform backend configuration to find the bucket name (See ih-plan --help).
    - It will refuse to delete a file if it ends with a ".state".
    """
    s3_client = get_s3_client(role=ctx.obj["aws_assume_role_arn"])
    bucket = ctx.obj["bucket"] or get_bucket(ctx.obj["tf_backend_file"])
    s3_client.delete_object(Bucket=bucket, Key=key_name)
    print(f"Successfully removed s3://{bucket}/{key_name}.")
