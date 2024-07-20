"""
.. topic:: ``utils.py``

    Various helper functions.
"""

import json
import os
import sys
from contextlib import contextmanager
from logging import getLogger
from os import getgid, getuid
from os import path as osp
from subprocess import CalledProcessError, Popen, check_call
from tempfile import TemporaryDirectory
from time import sleep, time

import boto3

from infrahouse_toolkit import DEFAULT_OPEN_ENCODING
from infrahouse_toolkit.cli.ih_s3_reprepro.aws import (
    assume_role,
    get_credentials_from_environ,
    get_credentials_from_profile,
)
from infrahouse_toolkit.cli.ih_s3_reprepro.gpg import gpg

DEPENDENCIES = ["reprepro", "gpg", "s3fs"]
LOG = getLogger()


def check_dependencies(binaries: list):
    """
    Ensure that dependencies are installed. The function calls each of the binary
    with a ``--help`` option.

    :param binaries: Dependency commands. List of strings.
    :type binaries: list
    """
    for dep in binaries:
        try:
            with open("/dev/null", "w", encoding=DEFAULT_OPEN_ENCODING) as devnull:
                LOG.debug("Checking if %s is installed.", dep)
                check_call([dep, "--help"], stdout=devnull, stderr=devnull)
        except FileNotFoundError:
            LOG.error("Looks like %s is not installed", dep)
            LOG.info("Try installing it by \n\n\tapt-get install %s\n", dep)
            sys.exit(1)


def mount_s3(bucket: str, path: str, role_arn: str = None, region: str = None):
    """
    Mount an S3 bucket at a path.

    :param bucket: AWS S3 bucket name.
    :type bucket: str
    :param path: Local filesystem path name.
    :type path: str
    :param role_arn: Assume role if specified.
    :param region: AWS region name.
    :type region: str
    """
    env = {}
    cmd = ["s3fs", bucket, path, "-o", f"uid={getuid()}", "-o", f"gid={getgid()}"]
    if role_arn:
        env = assume_role(role_arn)
        sts = boto3.client(
            "sts",
            aws_access_key_id=env["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=env["AWS_SECRET_ACCESS_KEY"],
            aws_session_token=env["AWS_SESSION_TOKEN"],
            region_name=region,
        )
        response = sts.get_caller_identity()
        LOG.debug("Assumed role: %s", response)
    elif "AWS_ACCESS_KEY_ID" in os.environ:
        env = get_credentials_from_environ()
    else:
        env = get_credentials_from_profile()

    LOG.debug("To reproduce environment: \n%s", "\n".join([f'export {key}="{value}"' for key, value in env.items()]))
    LOG.debug("Command to debug: mkdir -p %s; %s -o dbglevel=info -f -o curldbg", path, " ".join(cmd))
    execute(cmd, env=env)


def umount_s3(path: str):
    """
    Unmount an S3 bucket at a path.

    :param path: Local filesystem path name where the S3 bucket is mounted at.
    :type path: str
    """
    try:
        check_call(["umount", path])
    except CalledProcessError as err:
        LOG.exception(err)
        sys.exit(1)


@contextmanager
def local_s3(bucket, role_arn=None, retry_timeout=60, region=None) -> str:
    """
    Mount an S3 bucket locally and return a mount point.

    :param bucket: AWS S3 bucket name.
    :type bucket: str
    :param role_arn: Assume role if specified.
    :type role_arn: str
    :param retry_timeout: How many second to keep trying to mount the bucket.
    :type retry_timeout: int
    :param region: AWS region name.
    :type region: str
    :return: Local filesystem path where the S3 bucket is mounted at.
    """
    with TemporaryDirectory() as mnt_dir:
        try:
            now = time()
            timeout = now + retry_timeout
            while True:
                mount_s3(bucket, mnt_dir, role_arn=role_arn, region=region)
                if osp.exists(osp.join(mnt_dir, "conf/distributions")):
                    break
                LOG.warning("Waiting until s3://%s is mounted at %s", bucket, mnt_dir)
                sleep(1)
                if time() > timeout:
                    raise RuntimeError(f"s3://{bucket} is not mounted after {retry_timeout} seconds")
            yield mnt_dir
        except Exception as err:
            LOG.critical(err)
            raise

        finally:
            umount_s3(mnt_dir)


def execute(cmd: list, env: dict = None):
    """
    Execute a command and exit with 1 if the command raises CalledProcessError.

    :param cmd: A command to execute. It's passed to check_call() and therefore must be a list.
    :type cmd: list
    :param env: Pass a dictionary with environment
    :type env: dict
    """
    try:
        LOG.debug("Executing %s", " ".join(cmd))
        LOG.debug("Environment: %s", json.dumps(env, indent=4) if env else "None")
        with Popen(cmd, env=env) as proc:
            try:
                proc.communicate()
            except KeyboardInterrupt:
                LOG.info("Exiting on <ctrl>+c")
                proc.terminate()
                LOG.info("Process %s is terminated. Waiting for it to exit.", cmd[0])
                proc.wait(60)

    except CalledProcessError as err:
        LOG.exception(err)
        sys.exit(1)


@contextmanager
def repo_env(bucket, role_arn, gpg_key_secret_id, gpg_passphrase_secret_id, region=None):
    """
    Prepare locally a repo and GPG so "reprepro" can manage it.

    :param bucket: AWS S3 bucket with the repo. The repo must be in the root.
    :type bucket: str
    :param role_arn: Optional role ARN. If specified, AWS client will assume it.
    :type role_arn: str
    :param gpg_key_secret_id: AWS secretsmanager secret (name or ARN) that stores the private GPG key,
        needed by ``reprepro`` to sign the repo.
    :type gpg_key_secret_id: str
    :param gpg_passphrase_secret_id: AWS secretsmanager secret (name or ARN) that stores a passphrase for
        the private GPG key. Note, it's not the passphrase itself, it's a secret that stores it.
    :type gpg_passphrase_secret_id: str
    :param region: AWS region name.
    :type region: str
    :return: A tuple with two strings: Local filesystem directory with a mounted S3 bucket
        and GPG home directory.
    """
    with local_s3(bucket, role_arn, region=region) as path:
        with gpg(
            secret_key=gpg_key_secret_id, role_arn=role_arn, secret_passphrase=gpg_passphrase_secret_id, region=region
        ) as gpg_home:
            yield path, gpg_home
