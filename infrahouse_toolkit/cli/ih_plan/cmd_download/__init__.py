"""
.. topic:: ``ih-plan download``

    A ``ih-plan download`` subcommand.

    See ``ih-plan download --help`` for more details.
"""

from os import path as osp

import click

from infrahouse_toolkit.cli.lib import get_bucket, get_s3_client


@click.command(name="download")
@click.argument("key_name")
@click.argument("plan_file", required=False)
@click.pass_context
def cmd_download(ctx, key_name, plan_file):
    """
    Download a file from an S3 bucket.

    The specified plan file will be downloaded from the S3 bucket (See ih-plan --help)
    and saved in <plan_file>. By default, the destination file will be a basename of the <key_name>.

    """
    s3_client = get_s3_client(role=ctx.obj["aws_assume_role_arn"])
    bucket = ctx.obj["bucket"] or get_bucket(ctx.obj["tf_backend_file"])
    plan_file = plan_file or osp.basename(key_name)
    with open(plan_file, "wb") as f_desc:
        s3_client.download_fileobj(bucket, key_name, f_desc)
    print(f"Successfully downloaded s3://{bucket}/{key_name} and saved in {plan_file}.")
