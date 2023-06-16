"""
.. topic:: ``ih-plan upload``

    A ``ih-plan upload`` subcommand.

    See ``ih-plan upload --help`` for more details.
"""

from os import path as osp

import click

from infrahouse_toolkit.cli.lib import get_bucket, get_s3_client


@click.command(name="upload")
@click.option("--key-name", help="Path to the file in the S3 bucket. Default is pending/<plan_file>", default=None)
@click.argument("plan_file")
@click.pass_context
def cmd_upload(ctx, key_name, plan_file):
    """
    Upload a plan file to an S3 bucket.

    The specified plan file will be uploaded to the S3 bucket (See ih-plan --help)
    and will be available as

    s3://<bucket name>/<key_name>

    By default, the S3 url will be s3://<bucket name>/pending/<plan_file>
    """
    s3_client = get_s3_client(role=ctx.obj["aws_assume_role_arn"])
    bucket = ctx.obj["bucket"] or get_bucket(ctx.obj["tf_backend_file"])
    dst_name = key_name or osp.join("pending", plan_file)
    s3_client.upload_file(plan_file, bucket, dst_name)
    print(f"Successfully uploaded s3://{bucket}/{dst_name}.")
