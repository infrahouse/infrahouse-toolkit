import boto3
import click

from os import path as osp

from infrahouse_toolkit.cli.lib import get_bucket


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
    s3_client = boto3.client("s3")
    bucket = ctx.obj["bucket"] or get_bucket(ctx.obj["tf_backend_file"])
    plan_file = plan_file or osp.basename(key_name)
    with open(plan_file, "wb") as f:
        s3_client.download_fileobj(bucket, key_name, f)
    print(f"Successfully downloaded s3://{bucket}/{key_name} and saved in {plan_file}.")
